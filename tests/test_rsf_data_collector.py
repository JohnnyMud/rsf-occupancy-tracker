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


def test_csv_storage_uses_canonical_schema_and_skips_duplicate(tmp_path):
    settings = make_settings(tmp_path)
    record = collector.OccupancyRecord(
        timestamp_utc=datetime(2026, 7, 27, 20, 30, tzinfo=timezone.utc),
        occupancy_count=42,
        max_capacity=150,
    )

    assert collector.save_to_csv(record, settings.csv_path) is True
    assert collector.save_to_csv(record, settings.csv_path) is False

    with settings.csv_path.open(newline="", encoding="utf-8") as csv_file:
        rows = list(csv.DictReader(csv_file))

    assert tuple(rows[0]) == collector.CANONICAL_HEADERS
    assert len(rows) == 1
    assert rows[0]["timestamp_utc"] == "2026-07-27T20:30:00Z"
    assert rows[0]["percentage_capacity"] == "28.0"


def test_invalid_capacity_configuration_exits_early(monkeypatch):
    monkeypatch.setenv("DENSITY_API_URL", "https://example.test/occupancy")
    monkeypatch.setenv("DENSITY_API_KEY", "secret")
    monkeypatch.setenv("MAX_CAPACITY", "zero")

    with pytest.raises(collector.ConfigurationError, match="must be an integer"):
        collector.CollectorSettings.from_env()
