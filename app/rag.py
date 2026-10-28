"""
Modul RAG — mengubah knowledge base menjadi embedding, menyimpannya ke FAISS,
melakukan semantic search, lalu menghasilkan jawaban menggunakan LLM.

Alur ini serupa dengan yang sudah dibangun di Assignment 3 (Semantic Search &
LLM Application) dan Sesi 11 (Building a Simple RAG System) — di assignment ini,
alur tersebut dibungkus menjadi fungsi yang dipanggil oleh router.py.
"""

import os
import pandas as pd
import numpy as np
import faiss
from google import genai
from google.genai import types

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KNOWLEDGE_BASE_PATH = os.path.join(BASE_DIR, "data", "it_helpdesk_knowledge_base.csv")
INDEX_PATH = os.path.join(BASE_DIR, "data", "faiss_index.bin")
EMBEDDINGS_PATH = os.path.join(BASE_DIR, "data", "embeddings.npy")

# Model constants
EMBEDDING_MODEL = "gemini-embedding-001"
LLM_MODEL = "gemini-3.5-flash"

_client = None
_index = None
_documents = None
_df = None


def get_genai_client():
    """Menginisialisasi genai.Client secara lazy menggunakan GEMINI_API_KEY dari environment."""
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY environment variable tidak ditemukan. "
                "Harap set API key di .env atau environment variables."
            )
        _client = genai.Client(api_key=api_key)
    return _client


def _get_embedding(text: str) -> list:
    """Menghasilkan representasi vektor teks menggunakan Gemini Embeddings API."""
    client = get_genai_client()
    result = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
    )
    return result.embeddings[0].values


def build_index():
    """
    Membangun index FAISS dari knowledge base CSV.
    Mendukung caching ke file binary (faiss_index.bin & embeddings.npy)
    agar startup server cepat dan efisien.
    """
    global _index, _documents, _df

    # Resolusi path CSV
    csv_file = KNOWLEDGE_BASE_PATH
    if not os.path.exists(csv_file):
        alt = os.path.join("data", "it_helpdesk_knowledge_base.csv")
        if os.path.exists(alt):
            csv_file = alt
        else:
            raise FileNotFoundError(f"Knowledge base CSV tidak ditemukan di {csv_file}")

    _df = pd.read_csv(csv_file)
    _df["content"] = "Q: " + _df["question"].astype(str).str.strip() + " A: " + _df["answer"].astype(str).str.strip()
    _documents = _df["content"].tolist()

    # Cek apakah cache embedding dan FAISS index sudah ada
    if os.path.exists(INDEX_PATH) and os.path.exists(EMBEDDINGS_PATH):
        try:
            embeddings = np.load(EMBEDDINGS_PATH)
            _index = faiss.read_index(INDEX_PATH)
            if _index.ntotal == len(_df):
                print(f"[RAG] Berhasil memuat FAISS index dari cache ({_index.ntotal} vektor).")
                return _index
        except Exception as e:
            print(f"[RAG] Gagal membaca cache index ({e}), membuat ulang...")

    print(f"[RAG] Menghasilkan embedding untuk {len(_documents)} entri knowledge base...")
    embeddings_list = []
    for doc in _documents:
        emb = _get_embedding(doc)
        embeddings_list.append(emb)

    embeddings = np.array(embeddings_list).astype("float32")
    dimension = embeddings.shape[1]

    # Inisialisasi FAISS Index berbasis Euclidean distance (L2)
    _index = faiss.IndexFlatL2(dimension)
    _index.add(embeddings)

    # Simpan cache ke disk
    try:
        np.save(EMBEDDINGS_PATH, embeddings)
        faiss.write_index(_index, INDEX_PATH)
        print(f"[RAG] FAISS index berhasil disimpan ke {INDEX_PATH} ({_index.ntotal} vektor).")
    except Exception as e:
        print(f"[RAG] Gagal menyimpan cache index ke disk: {e}")

    return _index


def ensure_initialized():
    """Memastikan index dan data knowledge base telah dimuat ke memori."""
    global _index
    if _index is None:
        build_index()


def semantic_search(query: str, top_k: int = 3):
    """
    Melakukan semantic search terhadap FAISS index berdasarkan embedding query.
    Mengembalikan daftar entri FAQ paling relevan beserta distance score-nya.
    """
    ensure_initialized()

    query_embedding = np.array([_get_embedding(query)]).astype("float32")
    distances, indices = _index.search(query_embedding, top_k)

    results = []
    for rank, idx in enumerate(indices[0]):
        if idx < len(_df):
            results.append({
                "rank": rank + 1,
                "faq_id": int(_df.iloc[idx]["faq_id"]),
                "category": _df.iloc[idx]["category"],
                "question": _df.iloc[idx]["question"],
                "answer": _df.iloc[idx]["answer"],
                "distance": float(distances[0][rank])
            })
    return results


async def answer_from_knowledge_base(query: str) -> str:
    """
    Fungsi yang dipanggil router.py ketika intent = 'faq'.
    Menjalankan semantic search, menyusun prompt terstruktur (Persona/Task/Context/Format),
    lalu memanggil LLM untuk menghasilkan jawaban yang grounded dan bebas halusinasi.
    """
    try:
        search_results = semantic_search(query, top_k=3)

        # Ambang batas relevansi semantik: query in-domain <= 0.50, out-of-scope > 0.55
        is_out_of_scope = search_results and search_results[0]["distance"] > 0.55

        context_str = "\n\n".join(
            f"[FAQ {r['rank']}] (Kategori: {r['category']})\n"
            f"Pertanyaan: {r['question']}\n"
            f"Jawaban: {r['answer']}"
            for r in search_results
        )

        prompt = f"""[Persona]
Kamu adalah asisten IT Helpdesk internal perusahaan yang ramah, sopan, profesional, dan solutif.

[Task]
Jawab pertanyaan pengguna HANYA berdasarkan informasi FAQ yang tersedia pada bagian Context di bawah ini.
Aturan Penting:
1. Jangan membuat asumsi, mengarang, atau menggunakan informasi di luar konteks FAQ yang diberikan.
2. Jika jawaban atas pertanyaan pengguna TIDAK terdapat dalam konteks FAQ, katakan dengan jujur dan sopan bahwa kamu belum memiliki informasi tersebut dalam knowledge base, lalu sarankan pengguna untuk menghubungi tim IT Support atau membuat tiket IT baru.
3. Gunakan bahasa Indonesia yang santun, jelas, dan langsung menjawab inti pertanyaan.

[Context]
{context_str}

[Format]
Berikan jawaban ringkas, akurat, dan solutif.

Pertanyaan Pengguna:
{query}

Jawaban IT Helpdesk:"""

        client = get_genai_client()
        try:
            response = client.models.generate_content(
                model=LLM_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.2),
            )
            return response.text.strip()
        except Exception as api_err:
            print(f"[RAG] Warning: LLM generation error ({api_err}). Menggunakan fallback konteks.")
            if is_out_of_scope:
                return (
                    "Mohon maaf, saya belum memiliki informasi mengenai hal tersebut dalam knowledge base kami. "
                    "Silakan hubungi tim IT Support langsung atau buat tiket IT baru untuk bantuan lebih lanjut."
                )
            top = search_results[0]
            return f"Berdasarkan informasi internal kami ({top['question']}):\n{top['answer']}"

    except Exception as e:
        return f"Mohon maaf, terjadi kendala saat memproses jawaban dari knowledge base: {str(e)}"
