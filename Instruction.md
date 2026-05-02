# KyberTune - LLMOps Kullanım Kılavuzu

KyberTune, yerel GPU gücünü Kubernetes orkestrasyonu ile birleştiren hibrit bir LLMOps boru hattıdır.

## 1. Mimari Yapı (Hibrit Model)
- **Eğitim (Host):** GPU performansını maksimize etmek için ana makinedeki Docker üzerinden çalışır.
- **Takip (Kubernetes):** MLflow sunucusu Kind cluster içinde çalışır ve tüm metrikleri merkezi olarak tutar.
- **Sunum (Serving):** Eğitilen modeller Kubernetes üzerinde mikroservis olarak yayına alınır.

## 2. Model Eğitimi Başlatma

Eğitimi başlatmak için ana dizinde şu komutu kullanabilirsiniz:
```bash
docker run --rm --runtime=nvidia --gpus all \
  -e MLFLOW_TRACKING_URI=http://localhost:5000 \
  -e MODEL_ID=microsoft/Phi-3-mini-4k-instruct \
  kybertune-training:latest
```

## 3. Serving (Modeli Yayına Alma)

Eğitilen modeli bir API olarak ayağa kaldırmak için:
1. MLflow'dan aldığınız `RUN_ID` değerini `infrastructure/serving-deployment.yaml` dosyasına girin.
2. Kubernetes'e uygulayın:
```bash
kubectl apply -f infrastructure/serving-deployment.yaml
```

## 4. MLflow RUN_ID Nasıl Bulunur?
1. Tarayıcınızda [http://localhost:5000](http://localhost:5000) adresini açın.
2. Sol taraftaki "KyberTune-FineTuning" deneyine tıklayın.
3. Listeden son başarılı eğitime (mavi check ikonlu) tıklayın.
4. Sayfanın en üstünde yer alan **Run ID** (Örn: `5a62f438...`) değerini kopyalayın.

## 5. Serving Testi (API Kullanımı)

Servis ayağa kalktıktan sonra aşağıdaki komutla modele soru sorabilirsiniz:
```bash
curl -X POST http://localhost:8000/generate \
     -H "Content-Type: application/json" \
     -d '{"prompt": "Human: What is Kubernetes? Assistant: ", "max_length": 50}'
```

## 6. Araçlara Erişim
- **MLflow UI:** [http://localhost:5000](http://localhost:5000)
- **Model API:** [http://localhost:8000/docs](http://localhost:8000/docs) (Swagger UI)

---
**Not:** Farklı bir model kullanırken modelin "HuggingFace Hub" üzerinde halka açık olduğundan veya `HF_TOKEN` ortam değişkeninin ayarlandığından emin olun.
