Customer Intelligence API (Flask + Cloud Run)

Production-ready Flask API that serves four ML capabilities built from the notebooks:

Churn classification (/predict → model_type: "churn")

Sales forecasting (/predict → model_type: "forecast")

RFM/KMeans clustering (/predict → model_type: "kmeans")

Text sentiment (/sentiment)

Runs locally with Python or in Docker, and deploys to Google Cloud Run via Artifact Registry.

Project structure
.
├─ app.py                     # Flask app (Gunicorn in Docker)
├─ requirements.txt           # Python deps (Dockerfile auto-cleans conda/mac lines)
├─ models/                    # <-- drop trained pickles here
│  ├─ churn_model.pkl
│  ├─ churn_models_all.pkl
│  ├─ linear_regressor_model.pkl
│  ├─ forecast_models.pkl
│  ├─ kmeans.pkl
│  └─ text_sentiment_model.pkl
├─ Dockerfile
└─ notebooks/                 # your training notebooks (optional)
   ├─ 1_eda.ipynb
   ├─ 2_clustering.ipynb
   ├─ 3_classification.ipynb
   ├─ 4_sales_forecasting.ipynb
   └─ 5_text_analysis.ipynb

Expected model files

app.py loads whichever exists:

Churn

Preferred: models/churn_model.pkl (dict with keys: model, feature_columns, numeric_columns, scaler (optional))

Fallback: models/churn_models_all.pkl (dict: feature_columns, numeric_columns, scaler, models mapping)

Forecast

Preferred: models/linear_regressor_model.pkl (or any regressor with .predict)

Fallback: models/forecast_models.pkl (dict: models mapping; optional feature_columns)

KMeans (RFM)

models/kmeans.pkl (dict: model, feature_columns (e.g., ["recency","frequency","monetary"]), scaler (optional), n_features)

Sentiment

models/text_sentiment_model.pkl

Either a VADER-like object with .polarity_scores(text)

or a dict { "vectorizer": <sklearn vectorizer>, "model": <clf>, "classes_": [...] }

Quick start (local)

Requires Python 3.12+

python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python app.py


App defaults to http://127.0.0.1:5000

Health check:

curl -s http://127.0.0.1:5000/ | jq

Docker (local)

Apple Silicon builds multi-arch images; we target linux/amd64 for Cloud Run.

docker buildx build --platform linux/amd64 \
  -t us-central1-docker.pkg.dev/incedo-capstone-469817/incedo-repo/incedo-capstone:latest .
docker run -p 8080:8080 \
  us-central1-docker.pkg.dev/incedo-capstone-469817/incedo-repo/incedo-capstone:latest


Health check:

curl -s http://127.0.0.1:8080/ | jq


Dockerfile notes

Cleans macOS/conda/@ file: lines in requirements.txt automatically.

Runs Gunicorn: app:app on $PORT (Cloud Run sets PORT).

Google Cloud deployment
One-time GCP setup
gcloud auth login
gcloud config set project incedo-capstone-469817
gcloud services enable run.googleapis.com artifactregistry.googleapis.com
gcloud auth configure-docker us-central1-docker.pkg.dev


Create the Artifact Registry repo (done once):

gcloud artifacts repositories create incedo-repo \
  --repository-format=docker --location=us-central1 \
  --description="Docker repo for Incedo Project"

Build → Push → Deploy (single command)
docker buildx build --platform linux/amd64 \
  -t us-central1-docker.pkg.dev/incedo-capstone-469817/incedo-repo/incedo-capstone:latest \
  . --push && \
gcloud run deploy incedo-capstone \
  --image us-central1-docker.pkg.dev/incedo-capstone-469817/incedo-repo/incedo-capstone:latest \
  --platform=managed --region=us-central1 --allow-unauthenticated --port=8080


The command prints a Service URL, e.g.:

https://incedo-capstone-45155634370.us-central1.run.app

API
1) Health

GET /

curl -s "$SERVICE_URL/" | jq
# {"message":"Customer Intelligence API is running."}

2) Predict (POST /predict)

Common body fields:

model_type: "churn" | "forecast" | "kmeans"

features: either

dict ⇒ keys auto-aligned to the model’s feature_columns

list ⇒ must be in the exact training order (use dict if unsure)

Churn – dict (recommended)
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

Churn – list (order must match training columns!)
curl -s "$SERVICE_URL/predict" -X POST -H "Content-Type: application/json" -d '{
  "model_type": "churn",
  "features": [24, 65.5, 0, 1, 1, 0, 1, 0]
}' | jq

Forecast (sales) – dict (recommended)
curl -s "$SERVICE_URL/predict" -X POST -H "Content-Type: application/json" -d '{
  "model_type": "forecast",
  "features": {
    "t": 49,
    "aov": 72.3,
    "orders": 104500,
    "customers": 83500,
    "compound": 0.12,
    "pos": 0.21, "neu": 0.72, "neg": 0.07,
    "m_2": 0, "m_3": 0, "m_4": 0, "m_5": 0, "m_6": 0, "m_7": 0,
    "m_8": 0, "m_9": 0, "m_10": 0, "m_11": 0, "m_12": 1
  }
}' | jq


If you get X has N features, but ... expects M, switch to a dict and include the exact one-hot month flags your model used (e.g., m_2..m_12) and any exogenous columns (aov, orders, customers, compound/neg/neu/pos, etc).

KMeans (RFM) – dict
curl -s "$SERVICE_URL/predict" -X POST -H "Content-Type: application/json" -d '{
  "model_type": "kmeans",
  "features": { "recency": 12, "frequency": 8, "monetary": 420.0 }
}' | jq

3) Sentiment (POST /sentiment)
curl -s "$SERVICE_URL/sentiment" -X POST -H "Content-Type: application/json" -d '{
  "text": "The product is fantastic and support was super helpful!"
}' | jq

Training → Exporting models

Use the notebooks in notebooks/ to train and export pickles into models/ using the filenames above.
Tip: When training with scikit-learn, set and persist feature_names_in_ or keep a feature_columns list with the saved artifact so the API can align dict inputs correctly.

Troubleshooting

ModuleNotFoundError: No module named 'flask'

Ensure requirements.txt includes runtime deps (e.g., Flask, gunicorn, numpy, pandas, scikit-learn).

Rebuild image.

Pip fails on @ file: or macOS paths during Docker build

The Dockerfile automatically removes mac/conda/temp paths with sed. Keep those lines out of requirements.txt if possible.

Feature count mismatch (X has N features, but model expects M)

Send features as a dict aligned to training feature_columns.

For sales forecasting, include the month one-hots (m_2..m_12) and any exogenous columns you trained with (aov, orders, customers, compound/neg/neu/pos, etc).

Apple Silicon (M1/M2/M3)

Always build with --platform linux/amd64 for Cloud Run.

Artifact Registry auth

Run gcloud auth configure-docker us-central1-docker.pkg.dev.

404 / Not Found

Use the root: GET / or the exact endpoints /predict, /sentiment.

Cloud Run may take a few seconds after deploy to become warm.

Useful commands

List images:

gcloud artifacts docker images list \
  us-central1-docker.pkg.dev/incedo-capstone-469817/incedo-repo


Tail logs:

gcloud run services describe incedo-capstone --region us-central1 --format='value(status.url)'
gcloud run logs read incedo-capstone --region us-central1 --stream


Roll a new deploy (latest local changes):

docker buildx build --platform linux/amd64 \
  -t us-central1-docker.pkg.dev/incedo-capstone-469817/incedo-repo/incedo-capstone:latest \
  . --push && \
gcloud run deploy incedo-capstone \
  --image us-central1-docker.pkg.dev/incedo-capstone-469817/incedo-repo/incedo-capstone:latest \
  --platform=managed --region=us-central1 --allow-unauthenticated --port=8080
