# =============================================================
# AUTO SGI — Dockerfile
# Python 3.11 + Chromium headless (Debian Bookworm slim)
# =============================================================

FROM python:3.11-slim-bookworm

# --- Dependências do sistema e Chromium ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    # fontes e libs necessárias para o Chrome renderizar páginas
    fonts-liberation \
    libglib2.0-0 \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    # utilitários
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# --- Variáveis do Chrome (fixas no container) ---
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# --- Diretório de trabalho ---
WORKDIR /app

# --- Dependências Python (camada separada para cache) ---
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Código da aplicação ---
COPY core/ ./core/
COPY api/  ./api/

# --- Volumes de dados (declaração; montagem feita no EasyPanel) ---
RUN mkdir -p /data/entradas /data/extraidas /data/controle /data/logs /data/resultado

# --- Porta exposta internamente ---
EXPOSE 8000

# --- Healthcheck (EasyPanel usa para saber se o container está ok) ---
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# --- Comando de inicialização ---
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
