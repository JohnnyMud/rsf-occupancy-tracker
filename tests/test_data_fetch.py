from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

import data_fetch as fetch

LOCAL_TZ = ZoneInfo("America/Los_Angeles")


def make_raw_rows() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": [
                "2025-04-01 15:00:00",  # Tuesday 8 AM PDT
                "2025-04-02 16:00:00",  # Wednesday 9 AM PDT
                "2025-04-05 19:00:00",  # Saturday 12 PM PDT
                "2025-04-06 10:00:00",  # Saturday 3 AM PDT, filtered out
            ],
            "percentage_capacity": ["20.00", "40.00", "30.00", "50.00"],
            "pst_timestamp": ["", "", "", ""],
        }
    )


def test_prepare_occupancy_data_is_pure_and_validated():
    prepared = fetch.prepare_occupancy_data(make_raw_rows())

    assert list(prepared.columns) == list(fetch.REQUIRED_COLUMNS)
    assert len(prepared) == 3
    assert prepared["weekday"].tolist() == ["Tuesday", "Wednesday", "Saturday"]
    assert prepared["hour"].tolist() == [8, 9, 12]
    assert prepared["percentage_capacity"].tolist() == [20.0, 40.0, 30.0]


def test_prepare_occupancy_data_rejects_empty_result():
    raw = pd.DataFrame(
        {
            "timestamp": ["2024-01-01 15:00:00"],
            "percentage_capacity": ["10.00"],
        }
    )

    with pytest.raises(ValueError, match="No occupancy readings remain"):
        fetch.prepare_occupancy_data(raw)


def test_build_heatmap_pivot_masks_saturday_evening():
    prepared = fetch.prepare_occupancy_data(make_raw_rows())
    evening = prepared.iloc[[0]].copy()
    evening["pst_timestamp"] = datetime(2025, 4, 5, 19, 0, tzinfo=LOCAL_TZ)
    evening["weekday"] = "Saturday"
    evening["hour"] = 19
    evening["pst_hour"] = "7 PM"
    evening["percentage_capacity"] = 55.0
    prepared = pd.concat([prepared, evening], ignore_index=True)

    pivot = fetch.build_heatmap_pivot(prepared)

    assert "7 PM" in pivot.columns
    assert pd.isna(pivot.loc["Saturday", "7 PM"])


def test_try_load_occupancy_data_returns_error_instead_of_raising(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("sheet unavailable")

    monkeypatch.setattr(fetch, "load_raw_sheet_data", boom)
    data, error = fetch.try_load_occupancy_data()

    assert data is None
    assert "sheet unavailable" in error


def test_app_imports_without_loading_sheet_data():
    import app

    assert callable(app.create_layout)
    assert app.app.layout is app.create_layout
