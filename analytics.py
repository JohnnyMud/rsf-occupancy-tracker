from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from data_fetch import DAY_ORDER, format_hour_label

PEAK_WINDOW_HOURS = 3


@dataclass(frozen=True)
class OccupancyInsights:
    avg_capacity: float
    total_readings: int
    date_start: str
    date_end: str
    days_with_data: list[str]
    missing_days: list[str]
    least_busy_day: str | None
    least_busy_day_avg: float | None
    least_busy_day_n: int
    most_busy_day: str | None
    most_busy_day_avg: float | None
    most_busy_day_n: int
    least_busy_hour: int | None
    least_busy_hour_avg: float | None
    least_busy_hour_n: int
    peak_hour: int | None
    peak_hour_avg: float | None
    peak_hour_n: int
    peak_period_start: int | None
    peak_period_end: int | None
    peak_period_label: str
    peak_period_avg: float | None
    peak_period_n: int


def _weekday_counts(df: pd.DataFrame) -> pd.Series:
    return df.groupby("weekday").size().reindex(DAY_ORDER).fillna(0).astype(int)


def _hourly_stats(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    grouped = df.groupby("hour")["percentage_capacity"]
    return grouped.mean(), grouped.size()


def find_peak_period(
    hourly_avgs: pd.Series,
    hourly_counts: pd.Series,
    window_size: int = PEAK_WINDOW_HOURS,
) -> tuple[int | None, int | None, float | None, int]:
    """Return the busiest contiguous hour window in the dataset."""
    if hourly_avgs.empty or window_size <= 0:
        return None, None, None, 0

    hours = sorted(int(hour) for hour in hourly_avgs.index)
    if len(hours) < window_size:
        best_hour = int(hourly_avgs.idxmax())
        return (
            best_hour,
            best_hour,
            float(hourly_avgs.loc[best_hour]),
            int(hourly_counts.loc[best_hour]),
        )

    best = None
    for start_hour in range(min(hours), max(hours) - window_size + 2):
        window = list(range(start_hour, start_hour + window_size))
        if not all(hour in hourly_avgs.index for hour in window):
            continue
        avg = float(hourly_avgs.loc[window].mean())
        count = int(hourly_counts.loc[window].sum())
        candidate = (start_hour, start_hour + window_size - 1, avg, count)
        if best is None or candidate[2] > best[2]:
            best = candidate

    if best is None:
        best_hour = int(hourly_avgs.idxmax())
        return (
            best_hour,
            best_hour,
            float(hourly_avgs.loc[best_hour]),
            int(hourly_counts.loc[best_hour]),
        )
    return best


def format_hour_range(start_hour: int | None, end_hour: int | None) -> str:
    if start_hour is None or end_hour is None:
        return "Insufficient data"
    if start_hour == end_hour:
        return format_hour_label(start_hour)
    # Inclusive hour buckets, e.g. 16-18 => 4 PM – 6 PM.
    return f"{format_hour_label(start_hour)} – {format_hour_label(end_hour)}"


def compute_insights(df: pd.DataFrame) -> OccupancyInsights:
    """Compute dashboard insights with explicit missing-data behavior."""
    if df is None or df.empty:
        raise ValueError("Cannot compute insights from an empty occupancy dataset")

    required = {"pst_timestamp", "weekday", "hour", "percentage_capacity"}
    missing_columns = required - set(df.columns)
    if missing_columns:
        raise ValueError(f"Occupancy data is missing columns: {sorted(missing_columns)}")

    weekday_avgs = (
        df.groupby("weekday")["percentage_capacity"].mean().reindex(DAY_ORDER).dropna()
    )
    weekday_counts = _weekday_counts(df)
    days_with_data = [day for day in DAY_ORDER if weekday_counts.loc[day] > 0]
    missing_days = [day for day in DAY_ORDER if weekday_counts.loc[day] == 0]

    if weekday_avgs.empty:
        raise ValueError("No weekday averages available for insights")

    hourly_avgs, hourly_counts = _hourly_stats(df)
    if hourly_avgs.empty:
        raise ValueError("No hourly averages available for insights")

    least_busy_day = str(weekday_avgs.idxmin())
    most_busy_day = str(weekday_avgs.idxmax())
    least_busy_hour = int(hourly_avgs.idxmin())
    peak_hour = int(hourly_avgs.idxmax())
    peak_start, peak_end, peak_avg, peak_n = find_peak_period(
        hourly_avgs,
        hourly_counts,
    )

    return OccupancyInsights(
        avg_capacity=float(df["percentage_capacity"].mean()),
        total_readings=int(len(df)),
        date_start=df["pst_timestamp"].min().strftime("%b %d, %Y"),
        date_end=df["pst_timestamp"].max().strftime("%b %d, %Y"),
        days_with_data=days_with_data,
        missing_days=missing_days,
        least_busy_day=least_busy_day,
        least_busy_day_avg=float(weekday_avgs.loc[least_busy_day]),
        least_busy_day_n=int(weekday_counts.loc[least_busy_day]),
        most_busy_day=most_busy_day,
        most_busy_day_avg=float(weekday_avgs.loc[most_busy_day]),
        most_busy_day_n=int(weekday_counts.loc[most_busy_day]),
        least_busy_hour=least_busy_hour,
        least_busy_hour_avg=float(hourly_avgs.loc[least_busy_hour]),
        least_busy_hour_n=int(hourly_counts.loc[least_busy_hour]),
        peak_hour=peak_hour,
        peak_hour_avg=float(hourly_avgs.loc[peak_hour]),
        peak_hour_n=int(hourly_counts.loc[peak_hour]),
        peak_period_start=peak_start,
        peak_period_end=peak_end,
        peak_period_label=format_hour_range(peak_start, peak_end),
        peak_period_avg=peak_avg,
        peak_period_n=peak_n,
    )


def sample_size_label(count: int) -> str:
    unit = "reading" if count == 1 else "readings"
    return f"n={count} {unit}"
