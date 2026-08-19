FROM python:3.11-slim

WORKDIR /app

# git is needed for the code-repo ingestion adapter (cloning framework repos);
# build-essential covers native deps some torch/transformers wheels pull in.
RUN apt-get update && apt-get install -y --no-install-recommends \
    git build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Install the CPU-only torch build first: plain `pip install torch` on Linux
# pulls in several GB of bundled NVIDIA CUDA libraries by default, which is
# both wasted bandwidth/disk and painfully slow to download — we only ever
# run bge-m3/bge-reranker on CPU here (the LLM itself is a remote Groq/
# OpenRouter API call), and a droplet has no GPU anyway.
RUN pip install --no-cache-dir "torch>=2.6" --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8060

CMD ["gunicorn", "-c", "gunicorn_conf.py", "app:app"]
