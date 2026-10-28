"""
Modul Tools — fungsi-fungsi "aksi" yang dipanggil router ketika intent
BUKAN pertanyaan informasi/kebijakan, melainkan permintaan spesifik
yang butuh pengecekan data langsung (bukan retrieval semantik).

Pola ini mengikuti konsep Tool Integration di Sesi 12.3.
"""

import os
import pandas as pd

# Menentukan jalur absolut ke mock_tickets.csv agar aman dijalankan dari direktori manapun
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOCK_TICKETS_PATH = os.path.join(BASE_DIR, "data", "mock_tickets.csv")


def get_ticket_status(ticket_id: str) -> str:
    """
    Mencari status tiket berdasarkan ticket_id pada data mock_tickets.csv.
    Jika ticket_id tidak ditemukan, kembalikan pesan yang informatif
    (bukan error yang membuat aplikasi crash).
    """
    if not ticket_id or not str(ticket_id).strip():
        return "ID tiket tidak disertakan atau formatnya tidak valid. Mohon sertakan nomor tiket (contoh: TICKET-0001)."

    clean_id = str(ticket_id).strip().upper()

    try:
        # Cek ketersediaan file mock_tickets.csv
        file_path = MOCK_TICKETS_PATH
        if not os.path.exists(file_path):
            alt_path = os.path.join("data", "mock_tickets.csv")
            if os.path.exists(alt_path):
                file_path = alt_path
            else:
                return f"Database tiket tidak ditemukan di {file_path}."

        df = pd.read_csv(file_path)

        # Cari baris dengan ticket_id yang cocok (case-insensitive)
        matched = df[df["ticket_id"].astype(str).str.strip().str.upper() == clean_id]

        if matched.empty:
            return (
                f"Tiket dengan ID '{clean_id}' tidak ditemukan dalam sistem. "
                "Harap periksa kembali nomor tiket Anda atau hubungi tim IT Support jika tiket baru saja dibuat."
            )

        row = matched.iloc[0]
        return (
            f"Tiket {row['ticket_id']} ({row['subject']}) saat ini berstatus '{row['status']}'. "
            f"Kategori: {row['category']}. Karyawan: {row['employee_name']}. "
            f"Terakhir diperbarui pada {row['last_update']}."
        )

    except Exception as e:
        return f"Terjadi kesalahan saat memeriksa data tiket: {str(e)}"
