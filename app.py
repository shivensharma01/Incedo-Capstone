from flask import Flask, request, jsonify
import numpy as np
import pickle

app = Flask(__name__)

# tiny loader
def _load(path):
    try:
        with open(path, "rb") as f:
            return pickle.load(f)
    except Exception:
        return None

# CHURN (classification)
# Prefer single best-artifact, else fall back to bundle.
_churn_art = _load("models/churn_model.pkl")
if _churn_art is None:
    _churn_all = _load("models/churn_models_all.pkl")  # classification notebook
    if _churn_all is None:
        churn_model = churn_cols = churn_num = churn_scaler = None
    else:
        churn_cols   = _churn_all.get("feature_columns")
        churn_num    = _churn_all.get("numeric_columns")
        base_scaler  = _churn_all.get("scaler")  # only used when variant says uses_scaler=True
        models_dict  = _churn_all["models"]      # name -> {model, uses_scaler, variant}

        # pick a sensible default variant
        pref_order = [
            "RandomForest_SMOTE", "RandomForest_BASE",
            "Logistic_SMOTE", "Logistic_BASE",
            "SVM_SMOTE", "SVM_BASE",
        ] + list(models_dict.keys())
        chosen_key = next((k for k in pref_order if k in models_dict), None)
        chosen = models_dict[chosen_key] if chosen_key else next(iter(models_dict.values()))
        churn_model  = chosen["model"]
        churn_scaler = base_scaler if chosen.get("uses_scaler", False) else None
else:
    churn_model  = _churn_art["model"]
    churn_cols   = _churn_art.get("feature_columns")
    churn_num    = _churn_art.get("numeric_columns")
    churn_scaler = _churn_art.get("scaler")

# FORECAST (regression)
reg_model = _load("models/linear_regressor_model.pkl")
if reg_model is None:
    _f_all = _load("models/forecast_models.pkl")
    if _f_all is not None:
        # choose RF if present, else LR, else first
        md = _f_all["models"]
        reg_model = md.get("RandomForestRegressor") or md.get("LinearRegression") or next(iter(md.values()))
    # else: stays None and endpoint will say it's missing

# Determine forecast feature columns if available
try:
    if reg_model is not None and hasattr(reg_model, "feature_names_in_"):
        forecast_cols = list(reg_model.feature_names_in_)  # sklearn preserves training column order
    else:
        forecast_cols = _f_all.get("feature_columns") if '_f_all' in globals() and _f_all else None
except Exception:
    forecast_cols = None


# KMEANS (RFM clustering)
km_art = _load("models/kmeans.pkl")
if isinstance(km_art, dict):
    kmeans_model  = km_art.get("model")
    kmeans_cols   = km_art.get("feature_columns")   # ["recency","frequency","monetary"]
    kmeans_scaler = km_art.get("scaler")
    kmeans_n      = km_art.get("n_features")
else:
    kmeans_model = kmeans_cols = kmeans_scaler = kmeans_n = None

# SENTIMENT
sentiment_obj = _load("models/text_sentiment_model.pkl")

# helpers
def _to_row(feats, cols=None):
    """list -> array; dict -> align to cols (fill 0.0)."""
    if isinstance(feats, (list, tuple)):
        return np.array(feats, dtype=float).reshape(1, -1)
    if isinstance(feats, dict):
        if cols is None:
            return np.array([feats[k] for k in feats], dtype=float).reshape(1, -1)
        return np.array([feats.get(c, 0.0) for c in cols], dtype=float).reshape(1, -1)
    raise ValueError("features must be list or dict")

# routes
@app.route("/")
def home():
    return jsonify({"message": "Customer Intelligence API is running."})

@app.route("/predict", methods=["POST"])
def predict():
    try:
        data = request.get_json(force=True)
        model_type = data.get("model_type")
        features   = data.get("features")

        if not model_type or features is None:
            return jsonify({"error": "Provide 'model_type' and 'features'."}), 400

        if model_type == "churn":
            if churn_model is None:
                return jsonify({"error": "Churn model not loaded. Export pickles from classification notebook."}), 500
            X = _to_row(features, cols=churn_cols)
            # scale only numeric cols if scaler is present
            if churn_scaler is not None and churn_cols and (churn_num is not None):
                idx = [churn_cols.index(c) for c in churn_num if c in churn_cols]
                if idx:
                    Xn = X[:, idx]
                    X[:, idx] = churn_scaler.transform(Xn)
            y = churn_model.predict(X)[0]
            out = {"prediction": int(y) if isinstance(y, (np.integer,)) else float(y)}
            if hasattr(churn_model, "predict_proba"):
                out["proba"] = churn_model.predict_proba(X)[0].tolist()
            return jsonify(out)

        elif model_type == "forecast":
            if reg_model is None:
                return jsonify({"error": "Forecast model not loaded. Export pickles from sales forecasting notebook."}), 500
            X = _to_row(features)  # list in trained order or dict
            yhat = float(reg_model.predict(X)[0])
            return jsonify({"prediction": yhat})

        elif model_type == "kmeans":
            if kmeans_model is None:
                return jsonify({"error": "KMeans model not loaded. Export from clustering notebook."}), 500
            X = _to_row(features, cols=kmeans_cols if isinstance(features, dict) else None)
            if kmeans_n is not None and X.shape[1] != int(kmeans_n):
                return jsonify({"error": f"Expected {kmeans_n} features, got {X.shape[1]}."}), 400
            if kmeans_scaler is not None:
                X = kmeans_scaler.transform(X)
            label = int(kmeans_model.predict(X)[0])
            return jsonify({"cluster": label})

        else:
            return jsonify({"error": "Invalid model_type. Use 'churn', 'forecast', or 'kmeans'."}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/sentiment", methods=["POST"])
def sentiment():
    try:
        if sentiment_obj is None:
            return jsonify({"error": "Sentiment model not loaded. Export from text analysis notebook."}), 500
        data = request.get_json(force=True)
        text = (data.get("text") or "").strip()
        if not text:
            return jsonify({"error": "Provide 'text' in body."}), 400

        # VADER analyzer?
        if hasattr(sentiment_obj, "polarity_scores"):
            s = sentiment_obj.polarity_scores(text)
            c = s.get("compound", 0.0)
            s["label"] = "positive" if c >= 0.05 else ("negative" if c <= -0.05 else "neutral")
            return jsonify({"text": text, "scores": s})

        # vectorizer + classifier dict?
        if isinstance(sentiment_obj, dict) and "vectorizer" in sentiment_obj and "model" in sentiment_obj:
            import pandas as pd
            Xv = sentiment_obj["vectorizer"].transform(pd.Series([text]))
            lab = sentiment_obj["model"].predict(Xv)[0]
            out = {"label": str(lab)}
            if hasattr(sentiment_obj["model"], "predict_proba"):
                out["proba"] = sentiment_obj["model"].predict_proba(Xv)[0].tolist()
                out["classes"] = sentiment_obj.get("classes_")
            return jsonify({"text": text, "scores": out})

        return jsonify({"error": "Unsupported sentiment model format."}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)