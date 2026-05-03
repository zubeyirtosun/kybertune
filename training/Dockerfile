FROM nvidia/cuda:12.1.1-devel-ubuntu22.04

# Install Python and dependencies
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install
COPY training/requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy training code and data
COPY training/ /app/training/
COPY data/ /app/data/

ENV PYTHONPATH=/app
ENV MLFLOW_TRACKING_URI=http://172.18.0.1:5000

# HuggingFace model cache — mount with -v ~/.cache/huggingface:/root/.cache/huggingface
VOLUME ["/root/.cache/huggingface"]

CMD ["python3", "training/train.py"]
