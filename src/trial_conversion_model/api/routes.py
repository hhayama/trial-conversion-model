import logging
from importlib.metadata import PackageNotFoundError, version

import pandas as pd
from fastapi import APIRouter

from trial_conversion_model.api.schemas import PredictionRequest, PredictionResponse
from trial_conversion_model.predict import load_model, predict_proba

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger("prediction")
router = APIRouter()

try:
  app_version = version("trial-conversion-model")
except PackageNotFoundError:
  app_version = "0.0.0"  # Fallback if something broke

# Load the model once, when the service starts, not on every request.
model = load_model()

def to_band(probability: float) -> str:
    """Turn a raw probability into a label a human can act on."""
    if probability < 0.33:
        return "low"
    if probability < 0.66:
        return "medium"
    return "high"


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "version": app_version}


@router.post("/predict", response_model=PredictionResponse)
def predict(request: PredictionRequest) -> PredictionResponse:
    """Predict conversion probability for a single live trial."""
    request_data = request.model_dump()
    df = pd.DataFrame([request_data])
    raw_prediction = predict_proba(model, aggregates=df)
    prediction_value = round(float(raw_prediction.iloc[0]), 4)
    band = to_band(prediction_value)

    logger.info(f"{request_data} -> probability={prediction_value} band={band}")

    result = PredictionResponse(conversion_probability=prediction_value, conversion_band=band)
    return result
