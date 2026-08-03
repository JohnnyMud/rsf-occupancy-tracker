import logging

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


def prepare_occupancy_data(raw_df: pd.DataFrame) -> pd.DataFrame:
    """Validate and transform raw sheet rows into analysis-ready occupancy data."""
    if raw_df is None or raw_df.empty:
        raise ValueError("Occupancy data is empty")

    df = raw_df.copy()
    df["pst_timestamp"] = parse_timestamps(df)
    df["percentage_capacity"] = parse_percentage_capacity(df)
    df = df.dropna(subset=["pst_timestamp", "percentage_capacity"])

    spring_break_end = pd.Timestamp("2025-03-31", tz=LOCAL_TIMEZONE)
    end_of_semester = pd.Timestamp("2025-05-05", tz=LOCAL_TIMEZONE)
    df = df[
        (df["pst_timestamp"] >= spring_break_end)
        & (df["pst_timestamp"] < end_of_semester)
    ]
    df = df[
        (df["pst_timestamp"].dt.hour >= 7) & (df["pst_timestamp"].dt.hour < 23)
    ]

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
    """Build the day/hour occupancy pivot used by the heatmap chart."""
    if data.empty:
        raise ValueError("Cannot build a heatmap pivot from empty occupancy data")

    pivot_table = data.pivot_table(
        index="weekday",
        columns="hour",
        values="percentage_capacity",
        aggfunc="mean",
    )
    pivot_table = pivot_table.reindex(DAY_ORDER)
    null_hrs = [hour for hour in pivot_table.columns if hour >= 18]
    if "Saturday" in pivot_table.index and null_hrs:
        pivot_table.loc["Saturday", null_hrs] = np.nan
    pivot_table.columns = [format_hour_label(int(hour)) for hour in pivot_table.columns]
    return pivot_table


def load_occupancy_data(
    spreadsheet_name: str | None = None,
    credentials_path: str | None = None,
) -> pd.DataFrame:
    """Load sheet data and return a validated analysis DataFrame."""
    raw_df = load_raw_sheet_data(spreadsheet_name, credentials_path)
    return prepare_occupancy_data(raw_df)


def try_load_occupancy_data(
    spreadsheet_name: str | None = None,
    credentials_path: str | None = None,
) -> tuple[pd.DataFrame | None, str | None]:
    """Load occupancy data, returning (data, error_message)."""
    try:
        return load_occupancy_data(spreadsheet_name, credentials_path), None
    except Exception as exc:
        LOGGER.exception("Failed to load occupancy data")
        return None, str(exc)
