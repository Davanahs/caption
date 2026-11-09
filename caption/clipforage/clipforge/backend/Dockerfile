FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    wget \
    fonts-noto-color-emoji \
    fontconfig \
    && fc-cache -fv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./backend/
RUN --mount=type=cache,target=/root/.cache/pip pip install --default-timeout=300 --retries=20 --prefer-binary --upgrade pip "setuptools<70" wheel
RUN --mount=type=cache,target=/root/.cache/pip pip install --default-timeout=300 --retries=20 --no-deps torch==2.3.0+cpu torchaudio==2.3.0+cpu --extra-index-url https://download.pytorch.org/whl/cpu
RUN --mount=type=cache,target=/root/.cache/pip pip install --default-timeout=300 --retries=20 --prefer-binary --no-build-isolation --no-deps openai-whisper==20231117
RUN --mount=type=cache,target=/root/.cache/pip pip install --default-timeout=300 --retries=20 --prefer-binary -r ./backend/requirements.txt

# Pre-download Whisper base model
RUN python -c "import whisper; whisper.load_model('base')"

COPY . ./backend/

RUN useradd -ms /bin/bash appuser && \
    mkdir -p /app/uploads /app/outputs && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000
