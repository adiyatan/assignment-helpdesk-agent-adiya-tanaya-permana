# IT Helpdesk Assistant — End-to-End RAG & AI Agent Backend API

> **Individual Assignment - AI Engineering Bootcamp**  
> **Topik:** Cloud Deployment & Containerization for AI (End-to-End RAG & AI Agent Development)

Aplikasi backend API cerdas untuk **IT Helpdesk Assistant** yang mengintegrasikan dua kapabilitas inti AI dalam satu arsitektur terpadu:
1. **Retrieval-Augmented Generation (RAG):** Menjawab pertanyaan informasi dan kebijakan umum perusahaan secara akurat berdasarkan *knowledge base* internal.
2. **Action / Tool Calling (Mini-Agent Workflow):** Mendeteksi ketika karyawan membutuhkan aksi atau pengecekan data spesifik (misalnya pengecekan status tiket perbaikan IT) dan mengambil data langsung dari database tiket secara terstruktur.

Seluruh sistem dikembangkan menggunakan **FastAPI**, dikelola menggunakan **Environment Variables** (tanpa *hardcoded* API key), dan dikonfigurasi siap jalan dalam **Container Docker**.

---

## 1. Problem Statement & Objective

### Latar Belakang & Objective
Tim *People & IT Operations* di perusahaan setiap harinya menerima ratusan pertanyaan dan permintaan repetitif dari karyawan. Sebagian besar pertanyaan tersebut terbagi ke dalam dua pola:
* Karyawan yang membutuhkan jawaban cepat mengenai panduan dan kebijakan perusahaan (misal jatah cuti, reset password VPN, prosedur instalasi software).
* Karyawan yang ingin mengetahui progres tiket kendala teknis yang sebelumnya sudah mereka laporkan (misal status tiket `TICKET-0005`).

Pencarian semantik murni (*semantic search*) saja tidak dapat menangani pengecekan status tiket secara dinamis karena status tiket adalah entitas data transaksional yang spesifik, bukan dokumen pengetahuan umum.

**Objective Sistem:**
* Membangun *intelligent router* yang secara otomatis mampu membedakan intent permintaan karyawan: apakah membutuhkan pencarian informasi (*information retrieval*) atau aksi pengecekan data (*data inspection/action*).
* Menyediakan endpoint tunggal `/ask` yang terstruktur, aman, dan modular untuk melayani kedua kebutuhan tersebut secara transparan bagi pengguna.

### Dua Jenis Permintaan Pengguna

| Jenis Permintaan | Karakteristik & Kebutuhan | Komponen Penanganan | Contoh Query Karyawan |
| :--- | :--- | :--- | :--- |
| **1. Pertanyaan Informasi / Kebijakan Umum (`faq`)** | Membutuhkan pencarian pemahaman makna atas dokumen panduan dan kebijakan internal perusahaan, lalu menyusun jawaban natural melalui LLM. | **RAG System** (FAISS Vector Store + Gemini LLM) | - *"Berapa jatah cuti tahunan saya?"*<br>- *"Bagaimana cara reset password VPN perusahaan?"*<br>- *"Apakah saya boleh menginstal software sendiri di laptop kantor?"* |
| **2. Pengecekan Data Spesifik / Aksi (`ticket_status`)** | Membutuhkan ekstraksi parameter entitas (`ticket_id`) dan pencarian data langsung pada basis data tiket, bukan pencarian kemiripan teks. | **Tool Call** (`get_ticket_status()`) | - *"Tolong cek status tiket TICKET-0005 saya"*<br>- *"Gimana progres tiket 0002 saya?"*<br>- *"Apakah tiket TICKET-0010 sudah selesai diperbaiki?"* |

### Batasan dan Asumsi
1. **Cakupan Data Tiket:** Modul *tool call* mengakses basis data tiket mock (`data/mock_tickets.csv`) dengan format ID tiket standar `TICKET-XXXX`.
2. **Grounding Knowledge Base:** Jawaban RAG dibatasi secara ketat (*grounded*) hanya pada dokumen `data/it_helpdesk_knowledge_base.csv`. Pertanyaan di luar cakupan akan ditolak secara sopan (*graceful degradation*).
3. **Format Input:** Pertanyaan diajukan dalam bahasa Indonesia melalui JSON payload pada endpoint `/ask`.

---

## 2. Desain Arsitektur & Workflow Sistem

### Diagram Alur Kerja (Workflow)

```
                       [ User Input / Query ]
                                  │
                                  ▼
                   ┌──────────────────────────────┐
                   │    Intent Detection Router   │
                   │ (LLM Classifier + Heuristic) │
                   └──────────────┬───────────────┘
                                  │
               ┌──────────────────┴──────────────────┐
               ▼ (intent == 'faq')                   ▼ (intent == 'ticket_status')
    ┌─────────────────────────────┐        ┌──────────────────────────────┐
    │          RAG Path           │        │        Tool Call Path        │
    │ 1. Embed query (Gemini)     │        │ 1. Ekstrak ticket_id (Regex) │
    │ 2. Semantic Search (FAISS)  │        │ 2. Query data/mock_tickets   │
    │ 3. Build Structured Prompt  │        │ 3. Format ticket status info │
    │ 4. Generate answer via LLM  │        └──────────────┬───────────────┘
    └──────────────┬──────────────┘                       │
                   │                                      │
                   └──────────────────┬───────────────────┘
                                      ▼
                           ┌─────────────────────┐
                           │ Structured Response │
                           │   (JSON Payload)    │
                           └─────────────────────┘
```

### Kriteria Pembeda Intent
* **Intent `ticket_status`**: Terdeteksi jika query mengandung intensi memeriksa/menanyakan progres laporan, kata kunci tiket, atau pola ID tiket (`TICKET-XXXX`, `tiket 0001`, dsb.).
* **Intent `faq`**: Terdeteksi jika query berupa pertanyaan umum mengenai prosedur, fasilitas, aturan kerja, cuti, akun, jaringan, atau peralatan kantor.
* **Pertanyaan Ambigu / Out-of-Scope**: Diarahkan ke jalur RAG; jika skor jarak kemiripan semantik ($L_2$ distance) melebihi ambang batas ($\text{distance} > 0.55$), sistem secara proaktif mengembalikan pesan penolakan yang ramah dan menyarankan untuk menghubungi IT Support langsung.

---

## 3. Struktur Direktori Proyek

```
it-helpdesk-assignment/
├── app/
│   ├── __init__.py      # Package marker
│   ├── main.py          # Entry point FastAPI, endpoint /health dan /ask
│   ├── router.py        # Intent detection, regex extraction, & routing
│   ├── rag.py           # Ingestion, embedding, FAISS index, semantic search, & LLM prompt
│   └── tools.py         # Mock ticket lookup tool call
├── data/
│   ├── it_helpdesk_knowledge_base.csv   # Dokumen FAQ perusahaan untuk RAG
│   ├── mock_tickets.csv                 # Basis data tiket karyawan untuk Tool Call
│   ├── faiss_index.bin                  # Cache binary index FAISS
│   └── embeddings.npy                   # Cache vektor embedding
├── Dockerfile           # Konfigurasi containerization Docker
├── .env.example         # Template konfigurasi environment variable
├── requirements.txt     # Daftar pustaka Python (FastAPI, FAISS, Gemini SDK, dll)
└── README.md            # Dokumentasi lengkap proyek
```

---

## 4. Panduan Menjalankan Aplikasi

### A. Menjalankan Secara Lokal (Tanpa Docker)

1. **Clone repository dan buka direktori:**
   ```bash
   git clone <link-repository>
   cd it-helpdesk-assignment
   ```

2. **Buat dan aktifkan virtual environment:**
   ```bash
   python -m venv venv
   # Di Windows:
   venv\Scripts\activate
   # Di Linux/macOS:
   source venv/bin/activate
   ```

3. **Install dependensi:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Siapkan konfigurasi `.env`:**
   Salin `.env.example` menjadi `.env` dan masukkan API key Gemini Anda:
   ```bash
   cp .env.example .env
   ```
   Isi file `.env`:
   ```env
   GEMINI_API_KEY=AIzaSy...
   ```

5. **Jalankan FastAPI server menggunakan Uvicorn:**
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
   Aplikasi akan aktif di `http://localhost:8000`. Dokumentasi interaktif Swagger UI dapat diakses di `http://localhost:8000/docs`.

---

### B. Menjalankan Menggunakan Docker

1. **Build Docker Image:**
   Pastikan Docker Engine / Docker Desktop telah aktif, lalu jalankan:
   ```bash
   docker build -t it-helpdesk-assistant .
   ```

2. **Jalankan Container dengan Environment Variable:**
   ```bash
   docker run -d -p 8000:8000 --env-file .env --name helpdesk-container it-helpdesk-assistant
   ```

3. **Verifikasi Container Berjalan:**
   ```bash
   docker ps
   curl http://localhost:8000/health
   ```

---

## 5. Hasil Pengujian 5 Skenario Evaluasi

Pengujian dilakukan secara menyeluruh terhadap endpoint `/ask` mencakup skenario pertanyaan kebijakan (*RAG path*), pengecekan status tiket (*Tool Call path*), dan pertanyaan di luar cakupan (*Out-of-Scope*):

### Tabel Hasil Pengujian

| Skenario | Kategori Pengujian | Query Uji Pengguna | Intent Terdeteksi | Status API | Respons / Data yang Dikembalikan | Observasi & Evaluasi |
| :---: | :--- | :--- | :---: | :---: | :--- | :--- |
| **#1** | **RAG Path** (Kebijakan Cuti) | *"Berapa jatah cuti tahunan saya?"* | `faq` | `success` | Karyawan tetap mendapat jatah 12 hari cuti tahunan yang dapat diambil setelah masa kerja minimal 3 bulan. | **Tepat.** Router mengarahkan ke RAG. Informasi jatah 12 hari cuti terekstrak akurat. |
| **#2** | **RAG Path** (Akses / VPN) | *"Bagaimana cara reset password VPN perusahaan?"* | `faq` | `success` | Reset password VPN dapat dilakukan mandiri melalui portal self-service IT, atau menghubungi tim IT Support jika akun terkunci. | **Tepat.** Router mengarahkan ke RAG. Prosedur mandiri self-service portal disampaikan jelas. |
| **#3** | **Tool Call Path** (Tiket Ada) | *"Tolong cek status tiket TICKET-0005 saya"* | `ticket_status` | `success` | Tiket TICKET-0005 (Reset password VPN gagal terus) saat ini berstatus 'Diproses'. Kategori: Access. Karyawan: Dedi Kurniawan. Terakhir diperbarui pada 2026-08-27. | **Tepat.** ID `TICKET-0005` berhasil diekstrak dan data tiket diambil langsung dari database. |
| **#4** | **Tool Call Path** (Tiket Tidak Ada) | *"Bisa tolong periksa status tiket TICKET-9999?"* | `ticket_status` | `success` | Tiket dengan ID 'TICKET-9999' tidak ditemukan dalam sistem. Harap periksa kembali nomor tiket Anda atau hubungi tim IT Support jika tiket baru saja dibuat. | **Tepat.** Menangani kondisi tiket tidak ditemukan secara informatif tanpa membuat aplikasi *crash*. |
| **#5** | **Out-of-Scope** (Di Luar FAQ) | *"Apakah ada lowongan magang software engineer di kantor ini?"* | `faq` | `success` | Mohon maaf, saya belum memiliki informasi mengenai hal tersebut dalam knowledge base kami. Silakan hubungi tim IT Support langsung atau buat tiket IT baru untuk bantuan lebih lanjut. | **Tepat (Anti-Halusinasi).** Sistem mendeteksi jarak semantik jauh ($L_2 > 0.55$) dan menolak menjawab secara sopan. |

---

## 6. Keterbatasan Sistem & Rekomendasi Pengembangan

1. **Ekstraksi Tiket Bersifat Deterministic Regex:**  
   Format penulisan saat ini mengasumsikan pola `TICKET-XXXX` atau `tiket [angka]`. Untuk penggunaan riil, dapat ditambahkan LLM Entity Extraction jika pengguna menyebutkan deskripsi masalah tanpa menyebutkan nomor tiket sama sekali.
2. **Ketergantungan Kuota Free-Tier API:**  
   Penyedia LLM gratis memiliki batas laju (*rate-limiting/quota*). Sistem saat ini telah dilengkapi arsitektur **Graceful Degradation** di mana bila kuota LLM mengalami limit, sistem secara otomatis menyajikan jawaban dari dokumen FAQ teratas tanpa menghentikan layanan.
3. **Status Percakapan Single-Turn:**  
   Aplikasi saat ini beroperasi per-request (*stateless*). Pada pengembangan skala enterprise, disarankan mengintegrasikan session-based memory (Redis / PostgreSQL) agar asisten dapat mengingat konteks percakapan multi-turn.
