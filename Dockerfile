FROM python:3.11-slim

# Instala dependências do sistema para Playwright + Chromium
RUN apt-get update && apt-get install -y \
    libnss3 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxkbcommon0 \
    libgbm1 \
    libasound2 \
    fonts-liberation \
    libappindicator3-1 \
    libxshmfence1 \
    wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install --with-deps chromium

COPY src/ ./src/

CMD ["python", "-m", "src.main", "--param", "187054551"]