# Image Python dùng chung cho init (migrate + mock + backfill + tài khoản), etl (scheduler) và backend (FastAPI)
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Font DejaVu có dấu tiếng Việt cho xuất PDF (ReportLab)
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY common ./common
COPY database ./database
COPY mockdata ./mockdata
COPY etl ./etl
COPY backend ./backend
COPY docker/bootstrap.sh ./docker/bootstrap.sh

# Chạy bằng user thường; thư mục ground truth của mock data cần quyền ghi
RUN sed -i 's/\r$//' docker/bootstrap.sh \
    && useradd --create-home --uid 10001 app \
    && mkdir -p mockdata/output \
    && chown -R app:app mockdata/output
USER app

CMD ["python", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
