from datetime import date

import pandas as pd
import pytest

import data_fetch as fetch


def make_raw_rows() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": [
                "2025-04-01 15:00:00",  # Tuesday 8 AM PDT
                "2025-04-02 16:00:00",  # Wednesday 9 AM PDT
                "2025-04-05 19:00:00",  # Saturday 12 PM PDT
                "2025-04-06 10:00:00",  # Saturday 3 AM PDT, closed
                "2025-04-06 02:00:00",  # Saturday 7 PM PDT, closed
            ],
            "percentage_capacity": ["20.33", "40.00", "30.00", "50.00", "55.00"],
            "pst_timestamp": ["", "", "", "", ""],
        }
    )


def test_prepare_occupancy_data_uses_weekday_hours_and_preserves_raw_values():
    prepared = fetch.prepare_occupancy_data(make_raw_rows())

    assert list(prepared.columns) == list(fetch.REQUIRED_COLUMNS)
    assert len(prepared) == 3
    assert prepared["weekday"].tolist() == ["Tuesday", "Wednesday", "Saturday"]
    assert prepared["hour"].tolist() == [8, 9, 12]
    assert prepared["percentage_capacity"].tolist() == [20.33, 40.0, 30.0]


def test_prepare_occupancy_data_rejects_empty_result():
    raw = pd.DataFrame(
        {
            "timestamp": ["2025-04-06 10:00:00"],  # Saturday 3 AM PDT
            "percentage_capacity": ["10.00"],
        }
    )

    with pytest.raises(ValueError, match="No occupancy readings remain"):
        fetch.prepare_occupancy_data(raw)


def test_inclusive_date_bounds_keep_full_end_day():
    raw = pd.DataFrame(
        {
            "timestamp": [
                "2025-04-01 15:00:00",  # included
                "2025-04-02 16:00:00",  # end day, included
                "2025-04-03 16:00:00",  # after end, excluded
            ],
            "percentage_capacity": ["10.00", "20.00", "30.00"],
        }
    )

    prepared = fetch.prepare_occupancy_data(
        raw,
        start_date=date(2025, 4, 1),
        end_date=date(2025, 4, 2),
    )

    assert len(prepared) == 2
    assert prepared["percentage_capacity"].tolist() == [10.0, 20.0]


def test_build_heatmap_pivot_masks_closed_and_missing_slots():
    prepared = fetch.prepare_occupancy_data(make_raw_rows())
    pivot = fetch.build_heatmap_pivot(prepared)

    assert "7 AM" in pivot.columns
    assert "7 PM" in pivot.columns
    assert pd.isna(pivot.loc["Saturday", "7 AM"])
    assert pd.isna(pivot.loc["Saturday", "7 PM"])
    assert pivot.loc["Saturday", "12 PM"] == pytest.approx(30.0)
    assert pd.isna(pivot.loc["Monday", "8 AM"])


def test_filter_summer_months_excludes_may_through_august_by_default():
    prepared = fetch.prepare_occupancy_data(
        pd.DataFrame(
            {
                "timestamp": [
                    "2025-04-01 15:00:00",  # April, keep
                    "2025-05-01 15:00:00",  # May, drop
                    "2025-07-01 15:00:00",  # July, drop
                    "2025-09-02 15:00:00",  # September, keep
                ],
                "percentage_capacity": ["10.00", "20.00", "30.00", "40.00"],
            }
        )
    )

    school_year = fetch.filter_summer_months(prepared, exclude=True)
    with_summer = fetch.filter_summer_months(prepared, exclude=False)

    assert school_year["percentage_capacity"].tolist() == [10.0, 40.0]
    assert with_summer["percentage_capacity"].tolist() == [10.0, 20.0, 30.0, 40.0]


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
