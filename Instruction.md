# KyberTune - Kullanım Kılavuzu

Bu proje, Kubernetes üzerinde çalışan jenerik bir LLMOps fine-tuning boru hattıdır. Altyapı, modelden bağımsız (model-agnostic) kurgulanmıştır.

## 1. Modeli Nasıl Değiştiririm?

Eğitilecek modeli değiştirmek için kodun içine girmenize gerek yoktur. Tüm süreç **Kubernetes Job** manifesti üzerinden yönetilir.

### Adımlar:
1. `infrastructure/training-job.yaml` dosyasını açın.
2. `env` bölümündeki `MODEL_ID` değerini istediğiniz HuggingFace model ID'si ile değiştirin:

```yaml
env:
- name: MODEL_ID
  value: "microsoft/Phi-4-mini-instruct" # Örn: "google/gemma-2-2b" veya "meta-llama/Llama-3.2-1B"
```

3. Kaydedip dosyayı Kubernetes'e uygulayın:
```bash
kubectl apply -f infrastructure/training-job.yaml
```

## 2. Eğitim Parametrelerini Özelleştirme

Aynı manifest üzerinden eğitimin derinliğini ve hızını da ayarlayabilirsiniz:

- **`MAX_STEPS`**: Eğitimin ne kadar süreceği (Örn: 100, 500, 1000).
- **`BATCH_SIZE`**: Aynı anda işlenecek veri miktarı (GPU belleğine göre ayarlanmalıdır).
- **`LEARNING_RATE`**: Öğrenme hızı (Varsayılan: 2e-4).

## 3. Altyapı Nasıl Çalışır?

1. **Trigger:** `data/dataset.jsonl` dosyasındaki veriler kullanılarak eğitim başlar.
2. **Training:** Script, `target_modules="all-linear"` parametresi sayesinde modelin tüm lineer katmanlarını otomatik olarak bulur ve LoRA uygular.
3. **Logging:** Tüm metrikler ve model ağırlıkları otomatik olarak **MLflow** üzerinde saklanır.
4. **Output:** Eğitim bittiğinde `/results/final_adapter` klasörü altında hazır bir model adaptörü oluşur.

---
**Not:** Farklı bir model kullanırken modelin "HuggingFace Hub" üzerinde halka açık olduğundan veya `HF_TOKEN` ortam değişkeninin ayarlandığından emin olun.
