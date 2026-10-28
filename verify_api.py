import os
import sys
import json
from fastapi.testclient import TestClient

sys.path.insert(0, r"D:\Project\Tugas4Rework\it_helpdesk_starter_repo")
from app.main import app

client = TestClient(app)

def test_endpoints():
    print("=== 1. TESTING /health ENDPOINT ===")
    r = client.get("/health")
    print(f"Status Code: {r.status_code}, Response: {r.json()}")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
    print("Health check passed!\n")

    print("=== 2. TESTING 5 REQUIRED SCENARIOS ON /ask ===")
    scenarios = [
        {
            "no": 1,
            "type": "RAG Path (Pertanyaan Kebijakan/Informasi - Cuti)",
            "query": "berapa jatah cuti tahunan saya?"
        },
        {
            "no": 2,
            "type": "RAG Path (Pertanyaan Kebijakan/Informasi - Akses/VPN)",
            "query": "bagaimana cara reset password VPN perusahaan?"
        },
        {
            "no": 3,
            "type": "Tool Call Path (Cek Status Tiket - Ada di Data)",
            "query": "tolong cek status tiket TICKET-0005 saya"
        },
        {
            "no": 4,
            "type": "Tool Call Path (Cek Status Tiket - Tidak Ada di Data)",
            "query": "bisa tolong periksa status tiket TICKET-9999?"
        },
        {
            "no": 5,
            "type": "Out-of-Scope / Pertanyaan di Luar Knowledge Base",
            "query": "apakah ada lowongan magang software engineer di kantor ini?"
        }
    ]

    test_results = []
    for s in scenarios:
        print(f"--- Skenario {s['no']}: [{s['type']}] ---")
        print(f"Query: \"{s['query']}\"")
        resp = client.post("/ask", json={"query": s["query"]})
        print(f"HTTP Status: {resp.status_code}")
        data = resp.json()
        print(f"API Response Intent: {data.get('intent')}")
        print(f"API Response Status: {data.get('status')}")
        print(f"API Response Data:\n{data.get('data')}")
        print("-" * 60 + "\n")
        test_results.append({
            "scenario": s,
            "response": data,
            "http_status": resp.status_code
        })

    print("All 5 scenarios executed successfully!")
    return test_results

if __name__ == "__main__":
    test_endpoints()
