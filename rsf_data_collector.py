import csv
import logging
import os
from dataclasses import dataclass
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import gspread
import requests
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

LOGGER = logging.getLogger(__name__)
LOCAL_TIMEZONE = ZoneInfo("America/Los_Angeles")
CANONICAL_HEADERS = (
    "timestamp_utc",
    "occupancy_count",
    "max_capacity",
    "percentage_capacity",
)
GOOGLE_SCOPES = (
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
)
OPERATING_HOURS = {
    0: (time(7), time(23)),
    1: (time(7), time(23)),
    2: (time(7), time(23)),
    3: (time(7), time(23)),
    4: (time(7), time(23)),
    5: (time(8), time(18)),
    6: (time(8), time(23)),
}


class ConfigurationError(ValueError):
    """Raised when required collector configuration is invalid."""


@dataclass(frozen=True)
class CollectorSettings:
    density_api_url: str
    density_api_key: str
    max_capacity: int
    spreadsheet_name: str
    credentials_path: Path
    csv_path: Path
    request_timeout_seconds: float
    force_collection: bool

    @classmethod
    def from_env(cls) -> "CollectorSettings":
        load_dotenv()

        density_api_url = os.getenv("DENSITY_API_URL", "").strip()
        density_api_key = os.getenv("DENSITY_API_KEY", "").strip()
        if not density_api_url:
            raise ConfigurationError("DENSITY_API_URL is required")
        if not density_api_key:
            raise ConfigurationError("DENSITY_API_KEY is required")

        try:
            max_capacity = int(os.getenv("MAX_CAPACITY") or "150")
        except ValueError as exc:
            raise ConfigurationError("MAX_CAPACITY must be an integer") from exc
        if max_capacity <= 0:
            raise ConfigurationError("MAX_CAPACITY must be greater than zero")

        try:
            timeout = float(os.getenv("REQUEST_TIMEOUT_SECONDS") or "10")
        except ValueError as exc:
            raise ConfigurationError("REQUEST_TIMEOUT_SECONDS must be numeric") from exc
        if timeout <= 0:
            raise ConfigurationError("REQUEST_TIMEOUT_SECONDS must be greater than zero")

        force_collection = os.getenv("FORCE_COLLECTION", "").lower() in {
            "1",
            "true",
            "yes",
        }
        return cls(
            density_api_url=density_api_url,
            density_api_key=density_api_key,
            max_capacity=max_capacity,
            spreadsheet_name=(os.getenv("SPREADSHEET_NAME") or "RSF_DATA").strip(),
            credentials_path=Path(
                os.getenv("GOOGLE_CREDENTIALS_PATH") or "credentials.json"
            ),
            csv_path=Path(os.getenv("DATA_FILE") or "rsf_gym_crowd_data.csv"),
            request_timeout_seconds=timeout,
            force_collection=force_collection,
        )


@dataclass(frozen=True)
class OccupancyRecord:
    timestamp_utc: datetime
    occupancy_count: float
    max_capacity: int

    @property
    def percentage_capacity(self) -> float:
        return (self.occupancy_count / self.max_capacity) * 100

    def as_mapping(self) -> dict[str, str | float | int]:
        return {
            "timestamp_utc": self.timestamp_utc.isoformat().replace("+00:00", "Z"),
            "occupancy_count": self.occupancy_count,
            "max_capacity": self.max_capacity,
            "percentage_capacity": round(self.percentage_capacity, 2),
        }


def collection_slot(now: datetime | None = None) -> datetime:
    """Return the current UTC half-hour slot used as the record key."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("Collection timestamps must be timezone-aware")
    current_utc = current.astimezone(timezone.utc)
    return current_utc.replace(
        minute=(current_utc.minute // 30) * 30,
        second=0,
        microsecond=0,
    )


def is_during_operating_hours(timestamp_utc: datetime) -> bool:
    local_timestamp = timestamp_utc.astimezone(LOCAL_TIMEZONE)
    opens_at, closes_at = OPERATING_HOURS[local_timestamp.weekday()]
    local_time = local_timestamp.time().replace(tzinfo=None)
    return opens_at <= local_time < closes_at


def build_http_session() -> requests.Session:
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        status=3,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.mount("http://", HTTPAdapter(max_retries=retry))
    return session


def fetch_occupancy_count(
    settings: CollectorSettings,
    session: requests.Session | None = None,
) -> float:
    http = session or build_http_session()
    response = http.get(
        settings.density_api_url,
        headers={"Authorization": f"Bearer {settings.density_api_key}"},
        timeout=settings.request_timeout_seconds,
    )
    response.raise_for_status()

    try:
        payload: Any = response.json()
    except ValueError as exc:
        raise ValueError("Density API returned invalid JSON") from exc

    if not isinstance(payload, dict) or "count" not in payload:
        raise ValueError("Density API response must contain a count field")
    if isinstance(payload["count"], bool) or not isinstance(
        payload["count"], (int, float)
    ):
        raise ValueError("Density API count must be numeric")

    count = float(payload["count"])
    if count < 0:
        raise ValueError("Density API count cannot be negative")
    return count


def setup_google_sheets(
    spreadsheet_name: str | None = None,
    credentials_path: Path | str | None = None,
):
    resolved_credentials_path = Path(
        credentials_path
        or os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
    )
    if not resolved_credentials_path.is_file():
        raise ConfigurationError(
            f"Google credentials not found at {resolved_credentials_path}"
        )

    credentials = Credentials.from_service_account_file(
        resolved_credentials_path,
        scopes=GOOGLE_SCOPES,
    )
    client = gspread.authorize(credentials)
    spreadsheet = client.open(
        spreadsheet_name or os.getenv("SPREADSHEET_NAME", "RSF_DATA")
    )
    return spreadsheet.sheet1


def ensure_canonical_headers(worksheet) -> list[str]:
    headers = worksheet.row_values(1)
    if not headers:
        worksheet.append_row(list(CANONICAL_HEADERS))
        return list(CANONICAL_HEADERS)

    for header in CANONICAL_HEADERS:
        if header not in headers:
            headers.append(header)
            worksheet.update_cell(1, len(headers), header)
    return headers


def save_to_google_sheets(
    record: OccupancyRecord,
    settings: CollectorSettings,
) -> bool:
    worksheet = setup_google_sheets(
        settings.spreadsheet_name,
        settings.credentials_path,
    )
    headers = ensure_canonical_headers(worksheet)
    values = record.as_mapping()
    timestamp = str(values["timestamp_utc"])
    timestamp_column = headers.index("timestamp_utc") + 1

    if worksheet.find(timestamp, in_column=timestamp_column) is not None:
        LOGGER.info("Google Sheets already contains collection slot %s", timestamp)
        return False

    worksheet.append_row(
        [values.get(header, "") for header in headers],
        value_input_option="RAW",
    )
    return True


def save_to_csv(record: OccupancyRecord, csv_path: Path) -> bool:
    values = record.as_mapping()
    timestamp = str(values["timestamp_utc"])

    if csv_path.exists():
        with csv_path.open(newline="", encoding="utf-8") as csv_file:
            reader = csv.DictReader(csv_file)
            if tuple(reader.fieldnames or ()) != CANONICAL_HEADERS:
                raise ValueError(
                    f"{csv_path} uses a legacy schema; move or migrate it before collecting"
                )
            if any(row["timestamp_utc"] == timestamp for row in reader):
                LOGGER.info("CSV already contains collection slot %s", timestamp)
                return False

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not csv_path.exists()
    with csv_path.open("a", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CANONICAL_HEADERS)
        if write_header:
            writer.writeheader()
        writer.writerow(values)
    return True


def collect(settings: CollectorSettings, now: datetime | None = None) -> OccupancyRecord | None:
    timestamp = collection_slot(now)
    if not settings.force_collection and not is_during_operating_hours(timestamp):
        LOGGER.info(
            "Skipping collection outside RSF operating hours (%s)",
            timestamp.astimezone(LOCAL_TIMEZONE).isoformat(),
        )
        return None

    count = fetch_occupancy_count(settings)
    record = OccupancyRecord(
        timestamp_utc=timestamp,
        occupancy_count=count,
        max_capacity=settings.max_capacity,
    )
    save_to_csv(record, settings.csv_path)
    save_to_google_sheets(record, settings)
    LOGGER.info("Saved occupancy record for %s", record.as_mapping()["timestamp_utc"])
    return record


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        collect(CollectorSettings.from_env())
    except Exception:
        LOGGER.exception("Occupancy collection failed")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
