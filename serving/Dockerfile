FROM nvidia/cuda:12.1.1-base-ubuntu22.04

RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY serving/requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY serving/ /app/serving/

ENV PYTHONPATH=/app
ENV MLFLOW_TRACKING_URI=http://mlflow-service:5000

EXPOSE 8000

CMD ["python3", "serving/serve.py"]
