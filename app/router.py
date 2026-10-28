"""
Router — menentukan apakah query user butuh RAG (informasi/kebijakan)
atau tool call (aksi spesifik, misal cek status tiket).

Pola ini mengikuti workflow router yang sudah dipelajari di Sesi 12.4:
  user input -> intent detection -> jika butuh data -> retrieval (RAG)
                                 -> jika butuh aksi -> tool call
"""

import os
import re
from google import genai
from google.genai import types

from app.rag import answer_from_knowledge_base, get_genai_client, LLM_MODEL
from app.tools import get_ticket_status


async def detect_intent(query: str) -> str:
    """
    Menentukan intent dari query user. Harus mengembalikan salah satu:
      - "faq"           -> pertanyaan informasi/kebijakan, arahkan ke RAG
      - "ticket_status" -> permintaan cek status tiket, arahkan ke tool call

    Implementasi menggunakan LLM Gemini dengan prompt classification terstruktur,
    serta didukung heuristic fallback untuk keandalan maksimal.
    """
    clean_query = query.strip()
    if not clean_query:
        return "faq"

    # Heuristic fast check: jika mengandung pola ID tiket yang jelas, sangat kuat ke ticket_status
    if re.search(r"\b(?:ticket|tiket)[-_ ]?\d{1,5}\b", clean_query, re.IGNORECASE):
        return "ticket_status"

    # Intent detection via LLM
    try:
        client = get_genai_client()
        prompt = f"""Kamu adalah modul Router Intent Classifier untuk sistem IT Helpdesk.
Tugas: Klasifikasikan pertanyaan pengguna ke dalam salah satu dari dua kategori:
1. 'ticket_status': jika pengguna ingin memeriksa, melacak, atau mengetahui status dari suatu tiket/laporan/kendala teknis yang sebelumnya sudah diajukan (biasanya mengandung kata tiket, nomor tiket, atau ID tiket).
2. 'faq': jika pengguna menanyakan informasi umum, kebijakan kantor, prosedur pengajuan cuti, izin, password, perangkat laptop, akses VPN, aturan kerja, dsb.

Jawab HANYA dengan satu kata persis ('ticket_status' atau 'faq') tanpa tanda baca tambahan.

Pertanyaan Pengguna: {clean_query}

Klasifikasi:"""

        response = client.models.generate_content(
            model=LLM_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=10,
            ),
        )
        predicted = response.text.strip().lower()

        if "ticket" in predicted:
            return "ticket_status"
        elif "faq" in predicted:
            return "faq"
        else:
            return "faq"

    except Exception as e:
        print(f"[Router] Warning: LLM intent detection fallback due to {e}")
        # Rule-based fallback
        if re.search(r"\b(?:tiket|ticket|laporan|status tiket)\b", clean_query, re.IGNORECASE):
            return "ticket_status"
        return "faq"


def extract_ticket_id(query: str) -> str:
    """
    Mengekstrak ticket_id dari teks query.
    Format ticket_id pada mock_tickets.csv adalah 'TICKET-XXXX' (contoh: TICKET-0001).
    Mendukung variasi penulisan seperti 'ticket-0001', 'tiket 0005', 'TICKET_0010', dsb.
    """
    if not query:
        return ""

    # Pola 1: TICKET-0001, ticket_0005, ticket 0010
    match = re.search(r"\b(?:ticket|tiket)[-_ ]?(\d{1,5})\b", query, re.IGNORECASE)
    if match:
        digits = match.group(1)
        # Pad digits ke 4 digit jika perlu
        formatted_digits = digits.zfill(4)
        return f"TICKET-{formatted_digits}"

    # Pola 2: Format langsung TICKET-XXXX
    match2 = re.search(r"\b(TICKET-[A-Za-z0-9]+)\b", query, re.IGNORECASE)
    if match2:
        return match2.group(1).upper()

    return ""


async def handle_query(query: str) -> dict:
    """
    Fungsi utama yang dipanggil oleh endpoint /ask.
    Menjalankan intent detection, lalu merutekan ke RAG atau tool call yang sesuai.
    Mengembalikan dict dengan struktur: {"status": ..., "intent": ..., "data": ...}.
    """
    try:
        intent = await detect_intent(query)

        if intent == "ticket_status":
            ticket_id = extract_ticket_id(query)
            if not ticket_id:
                data = (
                    "Anda terdeteksi ingin mengecek status tiket, namun nomor tiket belum disertakan "
                    "atau formatnya belum sesuai. Mohon sertakan ID tiket Anda (contoh: TICKET-0001)."
                )
                return {"status": "success", "intent": "ticket_status", "data": data}

            data = get_ticket_status(ticket_id)
            return {"status": "success", "intent": "ticket_status", "data": data}

        elif intent == "faq":
            data = await answer_from_knowledge_base(query)
            return {"status": "success", "intent": "faq", "data": data}

        else:
            return {
                "status": "error",
                "intent": "unknown",
                "data": "Maaf, permintaan Anda tidak dapat diproses oleh sistem.",
            }

    except Exception as e:
        return {
            "status": "error",
            "intent": "error",
            "data": f"Terjadi kesalahan saat memproses permintaan: {str(e)}",
        }
