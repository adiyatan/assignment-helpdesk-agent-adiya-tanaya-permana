# Gunakan base image Python yang ramping
FROM python:3.11-slim

# Optimasi environment variable Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 1. Copy requirements.txt terlebih dahulu untuk memanfaatkan Docker layer caching
COPY requirements.txt .

# 2. Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# 3. Copy source code aplikasi dan folder data
COPY app/ ./app/
COPY data/ ./data/

# 4. Expose port 8000
EXPOSE 8000

# 5. Jalankan aplikasi FastAPI menggunakan uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
