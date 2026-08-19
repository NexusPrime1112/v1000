FROM python:3.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC
ENV PIP_NO_CACHE_DIR=1
ENV PYTHONUNBUFFERED=1
ENV CHROMIUM_PATH=/usr/bin/ungoogled-chromium
ENV NEXUS_CHROMIUM_BINARY=/usr/bin/ungoogled-chromium
ENV NEXUS_PROFILE_DIRECTORY=Default
ENV NEXUS_WINDOW_SIZE=1366x768
ENV NEXUS_DRIVER_BACKEND=undetected,selenium
ENV NEXUS_UC_USE_WEBDRIVER_MANAGER=1
ENV NEXUS_UC_USE_SUBPROCESS=1
ENV NEXUS_PREFER_SYSTEM_CHROMEDRIVER=0
ENV DISPLAY=:99
ENV NEXUS_PROFILE_PATH=/app/chromium
ENV OLLAMA_LLM_LIBRARY=cpu
ENV OLLAMA_HOST=http://127.0.0.1:11434
ENV OLLAMA_KEEP_ALIVE=20m
ENV NEXUS_PRIMARY_MODEL=qwen2.5:0.5b
ENV NEXUS_OLLAMA_MODELS=qwen2.5:0.5b,deepseek-coder:1.3b,tinyllama
ENV NEXUS_LLM_TIMEOUT_SECONDS=90

RUN apt-get update -qq && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        chromium \
        chromium-driver \
        curl \
        fonts-liberation \
        git \
        libopenblas0 \
        libvulkan1 \
        procps \
        zstd \
        xvfb && \
    ln -sf /usr/bin/chromium /usr/bin/ungoogled-chromium && \
    ln -sf /usr/bin/chromium /usr/bin/chromium-browser && \
    mkdir -p /tmp/ollama-dist /usr/lib/ollama && \
    curl -fsSL https://ollama.com/download/ollama-linux-amd64.tar.zst | \
      tar --zstd -x -C /tmp/ollama-dist \
        --exclude='*/runners/cuda*' \
        --exclude='*/runners/rocm*' \
        --exclude='*/cuda_v*' \
        --exclude='*/libcuda.so*' \
        --exclude='*/libcudart.so*' \
        --exclude='*/libggml-cuda*' \
        --exclude='*/rocm*' && \
    install -m 755 /tmp/ollama-dist/bin/ollama /usr/bin/ollama && \
    cp -a /tmp/ollama-dist/lib/ollama/. /usr/lib/ollama/ && \
    rm -rf /tmp/ollama-dist && \
    chmod +x /usr/bin/chromium /usr/bin/chromedriver /usr/bin/ungoogled-chromium /usr/bin/chromium-browser || true && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN mkdir -p /app/profile /app/data /app/runtime /app/chromium

COPY requirements.txt /tmp/requirements.txt
RUN python -m pip install --upgrade pip && \
    python -m pip install -r /tmp/requirements.txt

CMD ["bash"]
