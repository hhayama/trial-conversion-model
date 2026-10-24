import pandas as pd

from trial_conversion_model.features import add_features

VALID_TRIAL = {
    "sessions_day1": 0,
    "sessions_day2": 0,
    "sessions_day3": 0,
    "listen_sessions_3d": None,
    "total_minutes_3d": None,
    "country": "US",
    "device_type": "iOS",
}


def test_zero_session_trial_gets_zero_shares_not_nan():
    zeroes_df = pd.DataFrame(VALID_TRIAL, index=[0])
    df = add_features(zeroes_df)
    print(df)
    assert df.iloc[0]["day1_share"] == 0
    assert df.iloc[0]["listen_share"] == 0
    assert df.iloc[0]["avg_session_minutes"] == 0
    # TODO: write this one yourself, in three steps:
    #   1. Build a one-row DataFrame for a trial with nothing in it: zero
    #      sessions on each of the three days, zero listen sessions, and
    #      zero total minutes.
    #   2. Pass it through add_features.
    #   3. Assert that day1_share, listen_share and avg_session_minutes each
    #      come back as 0 rather than a missing value.
    # raise NotImplementedError
