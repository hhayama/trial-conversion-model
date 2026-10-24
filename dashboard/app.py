"""Dashboard over the scored cohorts and drift verdicts in the bucket.

Run: uv run streamlit run dashboard/app.py
"""

import io
import json
import os
import re
from pathlib import Path

import altair as alt
import boto3
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from trial_conversion_model.monitoring import DRIFT_SHARE, REFERENCE_KEY

DAYS = 30
METRICS_PATH = Path("models/metrics.json")
DRIFT_HELP = (
    "Each cohort's input features are compared with the training extract "
    f"({REFERENCE_KEY} in the bucket). Drift is flagged when at least "
    f"{DRIFT_SHARE:.0%} of features have drifted."
)
BUCKET_WIDTH = 0.05  # 20 buckets across 0-100%
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")

# Reference palette: one blue series, status colors for the drift verdict.
BLUE = "#2a78d6"
BAND_OUTER = "#cde2fb"
BAND_INNER = "#86b6ef"
GOOD = "#0ca30c"
CRITICAL = "#d03b3b"

load_dotenv(override=True)


def _s3():
    return boto3.client("s3"), os.environ["S3_BUCKET"]


def list_keys(prefix: str) -> list[str]:
    s3, bucket = _s3()
    keys = []
    for page in s3.get_paginator("list_objects_v2").paginate(
        Bucket=bucket, Prefix=prefix
    ):
        keys += [obj["Key"] for obj in page.get("Contents", [])]
    return keys


def _get(key: str) -> bytes:
    s3, bucket = _s3()
    return s3.get_object(Bucket=bucket, Key=key)["Body"].read()


@st.cache_data(ttl=600)
def load_predictions(days: int = DAYS) -> pd.DataFrame:
    """The most recent `days` scored cohorts, one row per trial."""
    dated = {
        DATE_RE.search(k).group(1): k
        for k in list_keys("predictions/scored_")
        if k.endswith(".csv") and DATE_RE.search(k)
    }
    frames = []
    for day in sorted(dated)[-days:]:
        df = pd.read_csv(io.BytesIO(_get(dated[day])))
        # score.py and backfill.py name the probability column differently.
        df = df.rename(columns={"prediction_prob": "conversion_probability"})
        frames.append(df.assign(cohort_date=pd.Timestamp(day)))
    return pd.concat(frames, ignore_index=True)


@st.cache_data(ttl=600)
def load_drift() -> pd.DataFrame:
    """One drift verdict per cohort date.

    The daily check writes cohort_<date>.json and the backfill writes
    drift_cohort_<date>.json; where a date has both, the real check wins.
    """
    rows = []
    for key in list_keys("monitoring/"):
        if not key.endswith(".json"):
            continue
        verdict = json.loads(_get(key))
        match = DATE_RE.search(verdict.get("name", key))
        if not match:
            continue
        rows.append(
            {
                "cohort_date": pd.Timestamp(match.group(1)),
                "drifted_share": float(verdict["drifted_share"]),
                "drift": bool(verdict["drift"]),
                "backfill": verdict.get("source") == "backfill",
            }
        )
    df = pd.DataFrame(rows).sort_values(["cohort_date", "backfill"])
    return df.drop_duplicates("cohort_date", keep="first").reset_index(drop=True)


def load_metrics() -> dict:
    if not METRICS_PATH.exists():
        return {}
    return json.loads(METRICS_PATH.read_text())


def predictions_chart(preds: pd.DataFrame) -> alt.Chart:
    daily = (
        preds.groupby("cohort_date")["conversion_probability"]
        .agg(
            mean="mean",
            p10=lambda s: s.quantile(0.10),
            p25=lambda s: s.quantile(0.25),
            p75=lambda s: s.quantile(0.75),
            p90=lambda s: s.quantile(0.90),
        )
        .reset_index()
    )
    base = alt.Chart(daily).encode(x=alt.X("cohort_date:T", title="Cohort date"))
    prob = alt.Axis(format="%")
    outer = base.mark_area(color=BAND_OUTER, opacity=0.7).encode(
        y=alt.Y("p10:Q", title="Conversion probability", axis=prob),
        y2="p90:Q",
    )
    inner = base.mark_area(color=BAND_INNER, opacity=0.7).encode(y="p25:Q", y2="p75:Q")
    line = base.mark_line(color=BLUE, strokeWidth=2).encode(y="mean:Q")
    points = base.mark_circle(color=BLUE, size=60).encode(
        y="mean:Q",
        tooltip=[
            alt.Tooltip("cohort_date:T", title="Cohort"),
            alt.Tooltip("mean:Q", title="Mean", format=".1%"),
            alt.Tooltip("p25:Q", title="p25", format=".1%"),
            alt.Tooltip("p75:Q", title="p75", format=".1%"),
            alt.Tooltip("p10:Q", title="p10", format=".1%"),
            alt.Tooltip("p90:Q", title="p90", format=".1%"),
        ],
    )
    return (outer + inner + line + points).properties(height=300)


def drift_chart(drift: pd.DataFrame) -> alt.Chart:
    drift = drift.assign(verdict=drift["drift"].map({True: "DRIFT", False: "OK"}))
    bars = (
        alt.Chart(drift)
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X(
                "yearmonthdate(cohort_date):O",
                title="Cohort date",
                axis=alt.Axis(format="%b %d", labelAngle=-45),
            ),
            y=alt.Y(
                "drifted_share:Q",
                title="Share of features drifted",
                axis=alt.Axis(format="%"),
                scale=alt.Scale(domain=[0, 1]),
            ),
            color=alt.Color(
                "verdict:N",
                scale=alt.Scale(domain=["OK", "DRIFT"], range=[GOOD, CRITICAL]),
                legend=alt.Legend(title="Verdict", orient="top"),
            ),
            tooltip=[
                alt.Tooltip("cohort_date:T", title="Cohort"),
                alt.Tooltip("verdict:N", title="Verdict"),
                alt.Tooltip("drifted_share:Q", title="Drifted", format=".0%"),
            ],
        )
    )
    threshold = (
        alt.Chart(pd.DataFrame({"y": [DRIFT_SHARE]}))
        .mark_rule(strokeDash=[6, 4], color="gray")
        .encode(y="y:Q")
    )
    return (bars + threshold).properties(height=260)


def cohort_chart(cohort: pd.DataFrame) -> alt.Chart:
    """Trials per probability bucket: 20 fixed buckets of 5 points each."""
    return (
        alt.Chart(cohort)
        .mark_bar(color=BLUE, cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X(
                "conversion_probability:Q",
                bin=alt.Bin(extent=[0, 1], step=BUCKET_WIDTH),
                title="Conversion probability",
                axis=alt.Axis(format="%"),
            ),
            y=alt.Y("count():Q", title="Trials"),
            tooltip=[
                alt.Tooltip(
                    "conversion_probability:Q",
                    bin=alt.Bin(extent=[0, 1], step=BUCKET_WIDTH),
                    title="Probability bucket",
                    format=".0%",
                ),
                alt.Tooltip("count():Q", title="Number of Trials"),
            ],
        )
        .properties(height=300)
    )


def main() -> None:
    st.set_page_config(page_title="Trial conversion model", layout="wide")
    st.title("Trial conversion model")

    preds = load_predictions()
    drift = load_drift()
    metrics = load_metrics()

    latest_date = preds["cohort_date"].max()
    latest = preds[preds["cohort_date"] == latest_date]
    last_drift = drift.iloc[-1]
    verdict = "DRIFT" if last_drift["drift"] else "OK"
    auc = metrics.get("test_auc")

    cohort_col, drift_col, auc_col = st.columns(3)
    cohort_col.metric(
        "Latest scored cohort",
        f"{latest_date:%Y-%m-%d}",
        f"{len(latest)} trials",
        delta_color="off",
        delta_arrow="off",
        border=True,
    )
    drift_col.metric(
        "Latest drift verdict",
        verdict,
        f"{last_drift['drifted_share']:.0%} of features drifted "
        f"({last_drift['cohort_date']:%Y-%m-%d})",
        delta_color="inverse" if last_drift["drift"] else "off",
        delta_arrow="off",
        border=True,
        help=DRIFT_HELP,
    )
    auc_col.metric(
        "Model test AUC",
        f"{auc:.4f}" if auc else "n/a",
        f"n_test = {metrics['n_test']}" if auc else None,
        delta_color="off",
        delta_arrow="off",
        border=True,
    )

    st.caption(
        f"Drift reference: the model's training data (`{REFERENCE_KEY}`). "
        f"Flagged when at least {DRIFT_SHARE:.0%} of features drift."
    )

    st.subheader(f"Predictions over the last {DAYS} days")
    st.caption("Daily mean; darker band is p25–p75, lighter band p10–p90.")
    st.altair_chart(predictions_chart(preds), width="stretch")

    st.subheader(f"Drift over the last {DAYS} days")
    st.caption(f"Dashed line: drift threshold ({DRIFT_SHARE:.0%} of features).")
    since = drift["cohort_date"].max() - pd.Timedelta(days=DAYS - 1)
    st.altair_chart(drift_chart(drift[drift["cohort_date"] >= since]), width="stretch")

    cohort_dates = sorted(preds["cohort_date"].unique(), reverse=True)
    st.subheader("Conversion probability")
    selected = st.selectbox(
        "Cohort",
        cohort_dates,
        format_func=lambda d: f"{pd.Timestamp(d):%Y-%m-%d}",
    )
    selected_cohort = preds[preds["cohort_date"] == selected]
    st.caption(
        f"{len(selected_cohort)} trials in the {pd.Timestamp(selected):%Y-%m-%d} "
        f"cohort, per {BUCKET_WIDTH:.0%}-wide probability bucket."
    )
    st.altair_chart(cohort_chart(selected_cohort), width="stretch")
    with st.expander("Table"):
        st.dataframe(selected_cohort.drop(columns="cohort_date"), hide_index=True)


main()
