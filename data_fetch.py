from __future__ import annotations

import logging
from datetime import date, datetime, time

import numpy as np
import pandas as pd

import rsf_data_collector as rsf

LOGGER = logging.getLogger(__name__)
LOCAL_TIMEZONE = "America/Los_Angeles"
REQUIRED_COLUMNS = (
    "pst_timestamp",
    "pst_hour",
    "weekday",
    "hour",
    "percentage_capacity",
)
DAY_ORDER = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]
# Hour buckets that appear on at least one operating day.
OPERATING_HOUR_BUCKETS = list(range(7, 23))
# Summer months are not representative of school-year occupancy.
SUMMER_MONTHS = (5, 6, 7, 8)


def load_raw_sheet_data(
    spreadsheet_name: str | None = None,
    credentials_path: str | None = None,
) -> pd.DataFrame:
    """Fetch the raw occupancy sheet. Performs network I/O."""
    sheet = rsf.setup_google_sheets(spreadsheet_name, credentials_path)
    values = sheet.get_all_values()
    if not values:
        raise ValueError("The occupancy Google Sheet is empty")
    headers = values[0]
    if not headers:
        raise ValueError("The occupancy Google Sheet is missing a header row")
    return pd.DataFrame(values[1:], columns=headers)


def parse_timestamps(df: pd.DataFrame) -> pd.Series:
    timestamps = None

    if "timestamp_utc" in df:
        timestamps = pd.to_datetime(
            df["timestamp_utc"].replace("", pd.NA),
            errors="coerce",
            utc=True,
        ).dt.tz_convert(LOCAL_TIMEZONE)

    if "pst_timestamp" in df:
        legacy_local = pd.to_datetime(
            df["pst_timestamp"].replace("", pd.NA),
            format="%m/%d/%Y %I:%M:%p",
            errors="coerce",
        ).dt.tz_localize(
            LOCAL_TIMEZONE,
            ambiguous="NaT",
            nonexistent="shift_forward",
        )
        timestamps = (
            legacy_local if timestamps is None else timestamps.fillna(legacy_local)
        )

    if "timestamp" in df:
        legacy_utc = pd.to_datetime(
            df["timestamp"].replace("", pd.NA),
            errors="coerce",
            utc=True,
        ).dt.tz_convert(LOCAL_TIMEZONE)
        timestamps = legacy_utc if timestamps is None else timestamps.fillna(legacy_utc)

    if timestamps is None:
        raise ValueError(
            "Occupancy data requires timestamp_utc, pst_timestamp, or timestamp"
        )
    return timestamps


def parse_percentage_capacity(df: pd.DataFrame) -> pd.Series:
    """Parse occupancy percentages without rounding or clipping."""
    if "percentage_capacity" in df:
        percentages = pd.to_numeric(df["percentage_capacity"], errors="coerce")
    else:
        percentages = pd.Series(np.nan, index=df.index, dtype=float)

    if {"occupancy_count", "max_capacity"}.issubset(df.columns):
        counts = pd.to_numeric(df["occupancy_count"], errors="coerce")
        capacities = pd.to_numeric(df["max_capacity"], errors="coerce")
        calculated = counts.div(capacities.where(capacities > 0)).mul(100)
        percentages = percentages.fillna(calculated)
    return percentages


def format_hour_label(hour: int) -> str:
    if hour == 0:
        return "12 AM"
    if hour < 12:
        return f"{hour} AM"
    if hour == 12:
        return "12 PM"
    return f"{hour - 12} PM"


def _as_local_date(value: date | datetime | str | pd.Timestamp | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    timestamp = pd.Timestamp(value)
    if pd.isna(timestamp):
        raise ValueError(f"Invalid date boundary: {value!r}")
    return timestamp.date()


def is_open_hour(weekday_name: str, hour: int) -> bool:
    weekday_index = DAY_ORDER.index(weekday_name)
    opens_at, closes_at = rsf.OPERATING_HOURS[weekday_index]
    return opens_at.hour <= hour < closes_at.hour


def during_operating_hours(timestamps: pd.Series) -> pd.Series:
    """Return a boolean mask for RSF operating hours by weekday."""
    if timestamps.empty:
        return pd.Series(dtype=bool)

    weekday = timestamps.dt.weekday
    local_time = timestamps.dt.time
    mask = pd.Series(False, index=timestamps.index)

    for weekday_index, (opens_at, closes_at) in rsf.OPERATING_HOURS.items():
        on_day = weekday == weekday_index
        mask = mask | (on_day & (local_time >= opens_at) & (local_time < closes_at))
    return mask


def apply_inclusive_date_bounds(
    timestamps: pd.Series,
    start_date: date | datetime | str | pd.Timestamp | None = None,
    end_date: date | datetime | str | pd.Timestamp | None = None,
) -> pd.Series:
    """
    Inclusive local-calendar-day filter.

    start_date and end_date keep every timestamp on those days
    (00:00:00 through 23:59:59.999999 local time).
    """
    mask = pd.Series(True, index=timestamps.index)
    start = _as_local_date(start_date)
    end = _as_local_date(end_date)

    if start is not None and end is not None and start > end:
        raise ValueError("start_date must be on or before end_date")

    if start is not None:
        start_ts = pd.Timestamp(datetime.combine(start, time.min), tz=LOCAL_TIMEZONE)
        mask &= timestamps >= start_ts
    if end is not None:
        end_ts = pd.Timestamp(datetime.combine(end, time.max), tz=LOCAL_TIMEZONE)
        mask &= timestamps <= end_ts
    return mask


def filter_summer_months(
    data: pd.DataFrame,
    exclude: bool = True,
) -> pd.DataFrame:
    """
    Optionally drop May–August readings.

    Summer occupancy is usually not representative of the school year, so the
    dashboard excludes these months by default.
    """
    if data is None or data.empty or not exclude:
        return data.copy() if data is not None else pd.DataFrame()
    if "pst_timestamp" not in data.columns:
        raise ValueError("Occupancy data requires pst_timestamp to filter summer months")
    return data[~data["pst_timestamp"].dt.month.isin(SUMMER_MONTHS)].copy()


def prepare_occupancy_data(
    raw_df: pd.DataFrame,
    start_date: date | datetime | str | pd.Timestamp | None = None,
    end_date: date | datetime | str | pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Validate and transform raw sheet rows into analysis-ready occupancy data."""
    if raw_df is None or raw_df.empty:
        raise ValueError("Occupancy data is empty")

    df = raw_df.copy()
    df["pst_timestamp"] = parse_timestamps(df)
    df["percentage_capacity"] = parse_percentage_capacity(df)
    df = df.dropna(subset=["pst_timestamp", "percentage_capacity"])

    if df.empty:
        raise ValueError("No valid occupancy timestamps or capacity values found")

    df = df[apply_inclusive_date_bounds(df["pst_timestamp"], start_date, end_date)]
    df = df[during_operating_hours(df["pst_timestamp"])]

    if df.empty:
        raise ValueError("No occupancy readings remain after filtering")

    df["hour"] = df["pst_timestamp"].dt.hour.astype(int)
    df["pst_hour"] = df["hour"].map(format_hour_label)
    df["weekday"] = df["pst_timestamp"].dt.day_name()
    df = df.loc[:, list(REQUIRED_COLUMNS)].reset_index(drop=True)

    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"Prepared occupancy data is missing columns: {missing}")
    if df["percentage_capacity"].isna().any():
        raise ValueError("Prepared occupancy data contains invalid capacity values")

    return df


def build_heatmap_pivot(data: pd.DataFrame) -> pd.DataFrame:
    """Build a day/hour pivot with closed hours and missing slots as NaN."""
    if data.empty:
        raise ValueError("Cannot build a heatmap pivot from empty occupancy data")

    pivot_table = data.pivot_table(
        index="weekday",
        columns="hour",
        values="percentage_capacity",
        aggfunc="mean",
    )
    pivot_table = pivot_table.reindex(index=DAY_ORDER, columns=OPERATING_HOUR_BUCKETS)

    for weekday_name in DAY_ORDER:
        for hour in OPERATING_HOUR_BUCKETS:
            if not is_open_hour(weekday_name, hour):
                pivot_table.loc[weekday_name, hour] = np.nan

    pivot_table.columns = [format_hour_label(int(hour)) for hour in pivot_table.columns]
    return pivot_table


def load_occupancy_data(
    spreadsheet_name: str | None = None,
    credentials_path: str | None = None,
    start_date: date | datetime | str | pd.Timestamp | None = None,
    end_date: date | datetime | str | pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Load sheet data and return a validated analysis DataFrame."""
    raw_df = load_raw_sheet_data(spreadsheet_name, credentials_path)
    return prepare_occupancy_data(raw_df, start_date=start_date, end_date=end_date)


def try_load_occupancy_data(
    spreadsheet_name: str | None = None,
    credentials_path: str | None = None,
    start_date: date | datetime | str | pd.Timestamp | None = None,
    end_date: date | datetime | str | pd.Timestamp | None = None,
) -> tuple[pd.DataFrame | None, str | None]:
    """Load occupancy data, returning (data, error_message)."""
    try:
        return (
            load_occupancy_data(
                spreadsheet_name,
                credentials_path,
                start_date=start_date,
                end_date=end_date,
            ),
            None,
        )
    except Exception as exc:
        LOGGER.exception("Failed to load occupancy data")
        return None, str(exc)
