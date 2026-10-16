from fastapi.testclient import TestClient

from trial_conversion_model.api.main import app

client = TestClient(app)

VALID_TRIAL = {
    "sessions_day1": 3,
    "sessions_day2": 2,
    "sessions_day3": 2,
    "listen_sessions_3d": 5,
    "total_minutes_3d": 180.0,
    "country": "US",
    "device_type": "iOS",
}

def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_predict_returns_a_probability_and_a_band():
    response = client.post("/predict", json=VALID_TRIAL)
    conversion_probability = response.json()["conversion_probability"]
    conversion_band = response.json()["conversion_band"]
    assert response.status_code == 200
    assert 0.0 <= conversion_probability <= 1.0
    assert conversion_band in ["low", "med", "high"]


def test_predict_rejects_a_request_missing_a_field():
    invalid_trial = VALID_TRIAL.copy()
    invalid_trial.pop("sessions_day1", None)
    response = client.post("/predict", json=invalid_trial)
    assert response.status_code == 422