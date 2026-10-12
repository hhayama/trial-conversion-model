from typing import Literal

from pydantic import BaseModel


class PredictionRequest(BaseModel):
    """One trial's first-3-day base aggregates, as the caller knows them."""
    # separate sessions per day
    sessions_day1: int
    sessions_day2: int
    sessions_day3: int
    # aggregated across 3 days
    listen_sessions_3d: int
    total_minutes_3d: int
    # Categorical Features
    country: Literal["US", "EU", "India", "Rest"]
    device_type: Literal["iOS", 'Web', 'Android']

class PredictionResponse(BaseModel):
    """What we send back: a probability and a band a human can act on."""
    conversion_probability: float
    conversion_band: Literal["low", "medium", "high"]
