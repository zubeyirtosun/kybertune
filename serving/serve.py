import os
import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel
import mlflow

app = FastAPI(title="KyberTune Serving API")

# Configuration
MODEL_ID = os.getenv("MODEL_ID", "microsoft/Phi-3-mini-4k-instruct")
RUN_ID = os.getenv("RUN_ID")
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")

class Query(BaseModel):
    prompt: str
    max_length: int = 100

# Global model and tokenizer
model = None
tokenizer = None

@app.on_event("startup")
def load_model():
    global model, tokenizer
    print(f"Loading base model: {MODEL_ID}")
    
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16
    )

    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=False)
    base_model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        quantization_config=bnb_config,
        device_map="auto",
        max_memory={0: "4GiB", "cpu": "6GiB"},
        trust_remote_code=False
    )

    if RUN_ID:
        print(f"Loading adapter from MLflow Run: {RUN_ID}")
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        adapter_path = mlflow.artifacts.download_artifacts(run_id=RUN_ID, artifact_path="model_adapter")
        model = PeftModel.from_pretrained(base_model, adapter_path)
        print("Adapter loaded and attached.")
    else:
        model = base_model
        print("Running with base model only (No RUN_ID provided).")

@app.post("/generate")
async def generate(query: Query):
    if not model or not tokenizer:
        raise HTTPException(status_code=503, detail="Model not loaded yet")
    
    inputs = tokenizer(query.prompt, return_tensors="pt").to("cuda")
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=query.max_length,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )
    
    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    return {"prompt": query.prompt, "response": response}

@app.get("/health")
def health():
    return {"status": "healthy", "model": MODEL_ID, "adapter": RUN_ID}

if __name__ == "__main__":
    import uvicorn
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    
    uvicorn.run(app, host=args.host, port=args.port)
