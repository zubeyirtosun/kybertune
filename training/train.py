import os
import torch
import mlflow
from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

def train():
    # 1. Configuration (Generic via ENV)
    model_id = os.getenv("MODEL_ID", "microsoft/Phi-3-mini-4k-instruct")
    dataset_path = os.getenv("DATASET_PATH", "data/dataset.jsonl")
    output_dir = os.getenv("OUTPUT_DIR", "./results")
    
    print(f"Starting training for model: {model_id}")
    
    # MLflow Setup
    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://172.18.0.1:5000"))
    mlflow.set_experiment("KyberTune-FineTuning")

    # 2. Load Tokenizer
    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=False)
    tokenizer.pad_token = tokenizer.eos_token

    # 3. Load Dataset
    dataset = load_dataset("json", data_files=dataset_path, split="train")
    
    def tokenize_function(examples):
        return tokenizer(examples["text"], truncation=True, padding="max_length", max_length=512)

    tokenized_dataset = dataset.map(tokenize_function, batched=True, remove_columns=["text"])

    # 4. Load Model with 4-bit Quantization
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16
    )

    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=False # Native support check
    )

    # 5. Prepare for LoRA
    model = prepare_model_for_kbit_training(model)
    
    lora_config = LoraConfig(
        r=int(os.getenv("LORA_R", 8)),
        lora_alpha=int(os.getenv("LORA_ALPHA", 16)),
        target_modules="all-linear",  # Automatically targets all linear layers
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM"
    )

    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # 6. Training Arguments
    training_args = TrainingArguments(
        output_dir=output_dir,
        per_device_train_batch_size=int(os.getenv("BATCH_SIZE", 1)),
        gradient_accumulation_steps=int(os.getenv("GRADIENT_ACC", 4)),
        learning_rate=float(os.getenv("LEARNING_RATE", 2e-4)),
        logging_steps=10,
        max_steps=int(os.getenv("MAX_STEPS", 10)),
        fp16=True,
        optim="paged_adamw_32bit",
        report_to="mlflow",
        save_strategy="no"
    )

    # 7. Trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset,
        data_collator=DataCollatorForLanguageModeling(tokenizer, mlm=False)
    )

    # 8. Start Training
    with mlflow.start_run() as run:
        mlflow.log_param("model_id", model_id)
        trainer.train()
        
        # Save Adapter
        adapter_path = f"{output_dir}/final_adapter"
        model.save_pretrained(adapter_path)
        mlflow.log_artifacts(adapter_path, artifact_path="model_adapter")
        
        print(f"Training completed. Model saved to MLflow Run ID: {run.info.run_id}")

if __name__ == "__main__":
    train()
