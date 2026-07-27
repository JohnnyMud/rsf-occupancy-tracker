import csv
from datetime import datetime, timezone
from pathlib import Path

import pytest

import rsf_data_collector as collector


def make_settings(tmp_path: Path) -> collector.CollectorSettings:
    return collector.CollectorSettings(
        density_api_url="https://example.test/occupancy",
        density_api_key="secret",
        max_capacity=150,
        spreadsheet_name="RSF_DATA",
        credentials_path=tmp_path / "credentials.json",
        csv_path=tmp_path / "occupancy.csv",
        request_timeout_seconds=5,
        force_collection=False,
    )


def test_collection_slot_is_timezone_aware_and_idempotent():
    now = datetime(2026, 7, 27, 20, 47, 12, tzinfo=timezone.utc)

    assert collector.collection_slot(now) == datetime(
        2026,
        7,
        27,
        20,
        30,
        tzinfo=timezone.utc,
    )


@pytest.mark.parametrize(
    ("timestamp", "expected"),
    [
        (datetime(2026, 7, 27, 14, 0, tzinfo=timezone.utc), True),
        (datetime(2026, 7, 28, 6, 0, tzinfo=timezone.utc), False),
        (datetime(2026, 8, 1, 15, 0, tzinfo=timezone.utc), True),
        (datetime(2026, 8, 2, 1, 0, tzinfo=timezone.utc), False),
        (datetime(2026, 1, 5, 15, 0, tzinfo=timezone.utc), True),
    ],
)
def test_operating_hours_use_berkeley_local_time(timestamp, expected):
    assert collector.is_during_operating_hours(timestamp) is expected


def test_fetch_occupancy_count_validates_and_uses_timeout(tmp_path):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"count": 42}

    class Session:
        def get(self, url, headers, timeout):
            assert url == "https://example.test/occupancy"
            assert headers == {"Authorization": "Bearer secret"}
            assert timeout == 5
            return Response()

    count = collector.fetch_occupancy_count(make_settings(tmp_path), Session())

    assert count == 42


def test_csv_storage_uses_existing_schema_and_skips_duplicate_slot(tmp_path):
    settings = make_settings(tmp_path)
    record = collector.OccupancyRecord(
        timestamp_utc=datetime(2026, 7, 27, 20, 34, tzinfo=timezone.utc),
        occupancy_count=42,
        max_capacity=150,
    )
    duplicate_slot = collector.OccupancyRecord(
        timestamp_utc=datetime(2026, 7, 27, 20, 48, tzinfo=timezone.utc),
        occupancy_count=40,
        max_capacity=150,
    )

    assert collector.save_to_csv(record, settings.csv_path) is True
    assert collector.save_to_csv(duplicate_slot, settings.csv_path) is False

    with settings.csv_path.open(newline="", encoding="utf-8") as csv_file:
        rows = list(csv.DictReader(csv_file))

    assert tuple(rows[0]) == collector.STORAGE_HEADERS
    assert len(rows) == 1
    assert rows[0]["timestamp"] == "2026-07-27 20:34:00"
    assert rows[0]["percentage_capacity"] == "28.0"


def test_google_sheets_write_leaves_formula_column_alone(tmp_path, monkeypatch):
    class Worksheet:
        appended_rows = []

        def row_values(self, row):
            assert row == 1
            return ["timestamp", "percentage_capacity", "pst_timestamp"]

        def col_values(self, column):
            assert column == 1
            return ["timestamp"]

        def append_row(self, values, value_input_option):
            self.appended_rows.append((values, value_input_option))

    worksheet = Worksheet()
    monkeypatch.setattr(
        collector,
        "setup_google_sheets",
        lambda spreadsheet_name, credentials_path: worksheet,
    )
    record = collector.OccupancyRecord(
        timestamp_utc=datetime(2026, 7, 27, 20, 4, tzinfo=timezone.utc),
        occupancy_count=32,
        max_capacity=150,
    )

    assert collector.save_to_google_sheets(record, make_settings(tmp_path)) is True
    assert worksheet.appended_rows == [
        (["2026-07-27 20:04:00", 21.33], "RAW")
    ]


def test_invalid_capacity_configuration_exits_early(monkeypatch):
    monkeypatch.setenv("DENSITY_API_URL", "https://example.test/occupancy")
    monkeypatch.setenv("DENSITY_API_KEY", "secret")
    monkeypatch.setenv("MAX_CAPACITY", "zero")

    with pytest.raises(collector.ConfigurationError, match="must be an integer"):
        collector.CollectorSettings.from_env()
