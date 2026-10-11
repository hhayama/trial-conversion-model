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


# Written for you, as the worked example. The two below follow the same
# shape: build a request, send it, state what should be true. Note that
# this one checks the status key rather than the whole response body, so
# that adding a field later does not fail a test that never meant to
# promise anything about it.
def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_predict_returns_a_probability_and_a_band():
    # TODO: post VALID_TRIAL to /predict and assert three things: that the
    # request succeeded, that the conversion probability sits between 0 and
    # 1, and that the band is one of low, medium or high.
    raise NotImplementedError


def test_predict_rejects_a_request_missing_a_field():
    # TODO: post VALID_TRIAL with one field taken out, and assert the
    # service turns it down with a 422. It does that only because your
    # schema declares the field required, so this test is what notices if
    # that ever quietly changes.
    raise NotImplementedError
