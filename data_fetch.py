import numpy as np
import pandas as pd

import rsf_data_collector as rsf


LOCAL_TIMEZONE = "America/Los_Angeles"


def get_df():
    sheet = rsf.setup_google_sheets()
    values = sheet.get_all_values()
    if not values:
        raise ValueError("The occupancy Google Sheet is empty")
    headers = values[0]
    return pd.DataFrame(values[1:], columns=headers)


def parse_timestamps(df):
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
        timestamps = legacy_local if timestamps is None else timestamps.fillna(legacy_local)

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


def parse_percentage_capacity(df):
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


def filter_gym_data():
    df = get_df()
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
        (df["pst_timestamp"].dt.hour >= 7)
        & (df["pst_timestamp"].dt.hour < 23)
    ]
    df = df.drop(columns=["timestamp"], errors="ignore")
    return df


data = filter_gym_data()

# Hour column
data["pst_hour"] = [
    (
        f"{tstamp.hour} AM"
        if tstamp.hour < 12
        else "12 PM"
        if tstamp.hour == 12
        else f"{tstamp.hour - 12} PM"
    )
    for tstamp in data["pst_timestamp"]
]

# Weekday column
data["weekday"] = data["pst_timestamp"].dt.day_name()

# 24hr format hour column
data["hour"] = [timestamp.hour for timestamp in data["pst_timestamp"]]

# Make columns ordered nicely
data = data[
    ["pst_timestamp", "pst_hour", "weekday", "hour", "percentage_capacity"]
]

# Pivot table for heatmap visualization
pivot_table = data.pivot_table(
    index="weekday",
    columns="hour",
    values="percentage_capacity",
    aggfunc="mean",
)
null_hrs = [hour for hour in pivot_table.columns if hour >= 18]
if "Saturday" in pivot_table.index:
    pivot_table.loc["Saturday", null_hrs] = np.nan
pivot_table.columns = [
    (
        f"{hour} AM"
        if hour < 12
        else "12 PM"
        if hour == 12
        else f"{hour - 12} PM"
    )
    for hour in pivot_table.columns
]
