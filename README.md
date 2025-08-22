Customer Intelligence API (Flask → Cloud Run)

Serve ML models for:

Churn classification (/predict with "model_type": "churn")

Sales forecasting (/predict with "model_type": "forecast")

RFM/KMeans clustering (/predict with "model_type": "kmeans")

Text sentiment (/sentiment)

Works locally (Python/Docker) and on Google Cloud Run via Artifact Registry.

Project Layout:

.
├─ app.py
├─ requirements.txt
├─ Dockerfile
├─ models/                    # put trained pickles here
│  ├─ churn_model.pkl                (preferred)
│  ├─ churn_models_all.pkl           (fallback bundle)
│  ├─ linear_regressor_model.pkl     (preferred)
│  ├─ forecast_models.pkl            (fallback bundle)
│  ├─ kmeans.pkl
│  └─ text_sentiment_model.pkl
└─ notebooks/ (optional)

## Expected pickle formats

Churn

Preferred: churn_model.pkl as a dict:
{"model", "feature_columns", "numeric_columns", "scaler"(optional)}

Fallback: churn_models_all.pkl as a dict with the above + models mapping.

Forecast

Preferred: linear_regressor_model.pkl (any regressor with .predict).

Fallback: forecast_models.pkl with {"models": {...}, "feature_columns"(optional)}

KMeans

kmeans.pkl as a dict: {"model","feature_columns","scaler"(optional),"n_features"}

Sentiment

Either a VADER-like object with .polarity_scores(text)

or a dict { "vectorizer": <sklearn>, "model": <clf>, "classes_": [...] }

Run locally (Python)
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python app.py
# → http://127.0.0.1:5000


## Health check:

curl -s http://127.0.0.1:5000/ | jq

Run locally (Docker)

Apple Silicon (M1/M2/M3): always build --platform linux/amd64 for Cloud Run parity.

docker buildx build --platform linux/amd64 \
  -t us-central1-docker.pkg.dev/incedo-capstone-469817/incedo-repo/incedo-capstone:latest .
docker run -p 8080:8080 \
  us-central1-docker.pkg.dev/incedo-capstone-469817/incedo-repo/incedo-capstone:latest
# → http://127.0.0.1:8080

Google Cloud (Artifact Registry + Cloud Run)
One-time setup
gcloud auth login
gcloud config set project incedo-capstone-469817
gcloud services enable run.googleapis.com artifactregistry.googleapis.com
gcloud auth configure-docker us-central1-docker.pkg.dev


Create repo (first time only):

gcloud artifacts repositories create incedo-repo \
  --repository-format=docker --location=us-central1 \
  --description="Docker repo for Incedo Project"

Build → Push → Deploy (single line)
docker buildx build --platform linux/amd64 \
  -t us-central1-docker.pkg.dev/incedo-capstone-469817/incedo-repo/incedo-capstone:latest . --push && \
gcloud run deploy incedo-capstone \
  --image us-central1-docker.pkg.dev/incedo-capstone-469817/incedo-repo/incedo-capstone:latest \
  --platform=managed --region=us-central1 --allow-unauthenticated --port=8080


After deploy, the command prints the Service URL, e.g.:

https://incedo-capstone-45155634370.us-central1.run.app

API usage
1) Health
curl -s "$SERVICE_URL/" | jq
# {"message":"Customer Intelligence API is running."}

2) Predictions

Endpoint: POST $SERVICE_URL/predict
Body keys:

model_type: "churn" | "forecast" | "kmeans"

features: dict (recommended) or list in exact training order

Churn (dict)
curl -s "$SERVICE_URL/predict" -X POST -H "Content-Type: application/json" -d '{
  "model_type": "churn",
  "features": {
    "tenure": 24,
    "monthly_charges": 65.5,
    "contract_two_year": 0,
    "contract_one_year": 1,
    "internet_service_fiber_optic": 1,
    "payment_method_credit_card": 0,
    "has_paperless_billing": 1,
    "senior_citizen": 0
  }
}' | jq

Forecast (dict)

Include the month one-hot dummies used during training (e.g., m_2..m_12) and any exogenous cols (e.g., aov, orders, customers, compound/pos/neu/neg, etc.).

curl -s "$SERVICE_URL/predict" -X POST -H "Content-Type: application/json" -d '{
  "model_type": "forecast",
  "features": {
    "t": 49,
    "aov": 72.3,
    "orders": 104500,
    "customers": 83500,
    "compound": 0.12,
    "pos": 0.21, "neu": 0.72, "neg": 0.07,
    "m_2": 0, "m_3": 0, "m_4": 0, "m_5": 0, "m_6": 0,
    "m_7": 0, "m_8": 0, "m_9": 0, "m_10": 0, "m_11": 0, "m_12": 1
  }
}' | jq

KMeans (dict)
curl -s "$SERVICE_URL/predict" -X POST -H "Content-Type: application/json" -d '{
  "model_type": "kmeans",
  "features": { "recency": 12, "frequency": 8, "monetary": 420.0 }
}' | jq

3) Sentiment

Endpoint: POST $SERVICE_URL/sentiment

curl -s "$SERVICE_URL/sentiment" -X POST -H "Content-Type: application/json" -d '{
  "text": "The product is fantastic and support was super helpful!"
}' | jq

Tips & troubleshooting

Feature count mismatch
If you see X has N features, but Model expects M:

Send features as a dict.

Include the exact training columns (month one-hots m_2..m_12 and any exogenous columns used).

Flask not found
Ensure runtime deps are in requirements.txt (e.g., Flask, gunicorn, numpy, pandas, scikit-learn), then rebuild.

Mac/conda paths in requirements
The Dockerfile auto-removes lines like @ file: or /Users/.... Keep requirements clean if possible.

Apple Silicon
Always build with --platform linux/amd64.

Useful commands

List images:

gcloud artifacts docker images list \
  us-central1-docker.pkg.dev/incedo-capstone-469817/incedo-repo


Tail logs:

gcloud run services describe incedo-capstone --region us-central1 --format='value(status.url)'
gcloud run logs read incedo-capstone --region us-central1 --stream


Redeploy latest:

docker buildx build --platform linux/amd64 \
  -t us-central1-docker.pkg.dev/incedo-capstone-469817/incedo-repo/incedo-capstone:latest . --push && \
gcloud run deploy incedo-capstone \
  --image us-central1-docker.pkg.dev/incedo-capstone-469817/incedo-repo/incedo-capstone:latest \
  --platform=managed --region=us-central1 --allow-unauthenticated --port=8080
