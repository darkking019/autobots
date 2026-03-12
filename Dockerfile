FROM python:3.11-slim

# evitar cache python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

# dependências sistema (Playwright + Chromium)
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
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# copiar requirements primeiro (melhora build)
COPY requirements.txt .

# instalar dependências sem cache
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# instalar chromium do playwright
RUN playwright install --with-deps chromium

# copiar código
COPY src ./src

# expor porta
EXPOSE 8000

# iniciar API
CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]