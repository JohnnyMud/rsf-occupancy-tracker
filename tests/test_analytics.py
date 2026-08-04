from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

import analytics
import data_fetch as fetch

LOCAL_TZ = ZoneInfo("America/Los_Angeles")


def make_prepared_frame() -> pd.DataFrame:
    rows = [
        ("2025-04-01 08:00:00", "Tuesday", 8, 20.0),
        ("2025-04-01 16:00:00", "Tuesday", 16, 70.0),
        ("2025-04-01 17:00:00", "Tuesday", 17, 80.0),
        ("2025-04-01 18:00:00", "Tuesday", 18, 75.0),
        ("2025-04-02 08:00:00", "Wednesday", 8, 15.0),
        ("2025-04-02 16:00:00", "Wednesday", 16, 60.0),
        ("2025-04-02 17:00:00", "Wednesday", 17, 65.0),
        ("2025-04-02 18:00:00", "Wednesday", 18, 55.0),
        ("2025-04-05 12:00:00", "Saturday", 12, 30.0),
    ]
    return pd.DataFrame(
        [
            {
                "pst_timestamp": datetime.fromisoformat(ts).replace(tzinfo=LOCAL_TZ),
                "pst_hour": fetch.format_hour_label(hour),
                "weekday": weekday,
                "hour": hour,
                "percentage_capacity": value,
            }
            for ts, weekday, hour, value in rows
        ]
    )


def test_compute_insights_finds_peak_period_and_sample_sizes():
    insights = analytics.compute_insights(make_prepared_frame())

    assert insights.total_readings == 9
    assert insights.date_start == "Apr 01, 2025"
    assert insights.date_end == "Apr 05, 2025"
    assert insights.least_busy_day == "Saturday"
    assert insights.least_busy_day_n == 1
    assert insights.most_busy_day == "Tuesday"
    assert insights.most_busy_day_n == 4
    assert insights.least_busy_hour == 8
    assert insights.peak_period_start == 16
    assert insights.peak_period_end == 18
    assert insights.peak_period_label == "4 PM – 6 PM"
    assert insights.peak_period_avg == pytest.approx((70 + 80 + 75 + 60 + 65 + 55) / 6)
    assert insights.peak_period_n == 6
    assert "Monday" in insights.missing_days
    assert "Thursday" in insights.missing_days


def test_compute_insights_rejects_empty_dataset():
    with pytest.raises(ValueError, match="empty occupancy dataset"):
        analytics.compute_insights(pd.DataFrame())


def test_sample_size_label():
    assert analytics.sample_size_label(1) == "n=1 reading"
    assert analytics.sample_size_label(12) == "n=12 readings"
