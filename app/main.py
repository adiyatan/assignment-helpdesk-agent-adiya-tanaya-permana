"""
Entry point aplikasi FastAPI — IT Helpdesk Assistant.

Alur endpoint utama:
  1. Menerima pertanyaan/permintaan dari user
  2. Meneruskan ke router (router.py) untuk menentukan intent
  3. Router memanggil RAG (rag.py) atau tool (tools.py) sesuai intent
  4. Mengembalikan response terstruktur ke client
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.router import handle_query
from app.rag import ensure_initialized


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup event: Inisialisasi knowledge base dan FAISS index saat server pertama kali start."""
    print("[FastAPI] Memulai inisialisasi modul RAG dan database FAISS...")
    try:
        ensure_initialized()
        print("[FastAPI] Inisialisasi RAG selesai. Server siap menerima request.")
    except Exception as e:
        print(f"[FastAPI] Peringatan: Gagal melakukan preload index pada startup ({e}). Akan diinisialisasi secara lazy.")
    yield
    print("[FastAPI] Mematikan service IT Helpdesk Assistant...")


app = FastAPI(
    title="IT Helpdesk Assistant API",
    description="Backend API IT Helpdesk cerdas yang mengintegrasikan RAG (kebijakan/informasi) dan Tool Calling (status tiket).",
    version="1.0.0",
    lifespan=lifespan,
)

# Middleware CORS untuk fleksibilitas integrasi client
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    query: str = Field(..., description="Pertanyaan atau permintaan dari pengguna", example="berapa jatah cuti tahunan saya?")


class AskResponse(BaseModel):
    status: str = Field(..., description="Status hasil pemrosesan ('success' atau 'error')")
    intent: str = Field(..., description="Intent yang terdeteksi ('faq', 'ticket_status', atau 'unknown')")
    data: str = Field(..., description="Jawaban dari RAG atau informasi status tiket dari Tool")


@app.get("/health", tags=["System"])
async def health():
    """Endpoint sederhana untuk health check service."""
    return {"status": "ok"}


@app.post("/ask", response_model=AskResponse, tags=["Agent"])
async def ask(request: AskRequest):
    """
    Endpoint utama IT Helpdesk Assistant.
    Menerima pertanyaan bebas dari pengguna (kebijakan umum ATAU pengecekan status tiket),
    merutekan ke modul yang tepat, dan mengembalikan response terstruktur.
    """
    if not request.query or not request.query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Field 'query' tidak boleh kosong.",
        )

    try:
        result = await handle_query(request.query)
        return AskResponse(**result)
    except Exception as e:
        return AskResponse(
            status="error",
            intent="error",
            data=f"Terjadi kesalahan internal pada server saat memproses pertanyaan: {str(e)}",
        )
