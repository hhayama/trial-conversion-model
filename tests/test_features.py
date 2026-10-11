import pandas as pd

from trial_conversion_model.features import add_features


def test_zero_session_trial_gets_zero_shares_not_nan():
    # TODO: write this one yourself, in three steps:
    #   1. Build a one-row DataFrame for a trial with nothing in it: zero
    #      sessions on each of the three days, zero listen sessions, and
    #      zero total minutes.
    #   2. Pass it through add_features.
    #   3. Assert that day1_share, listen_share and avg_session_minutes each
    #      come back as 0 rather than a missing value.
    raise NotImplementedError
