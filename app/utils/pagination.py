import base64
from datetime import datetime


def encode_cursor(updated_at: datetime, row_id: int) -> str:
    # Use microsecond precision to avoid collisions; ensure ISO string is consistent
    payload = f"{updated_at.isoformat(timespec='microseconds')}|{row_id}"
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("utf-8").rstrip("=")


def decode_cursor(cursor_str: str) -> tuple[datetime, int]:
    # Add missing '=' padding for base64 urlsafe
    padding = "=" * (-len(cursor_str) % 4)
    raw = base64.urlsafe_b64decode((cursor_str + padding).encode("utf-8")).decode(
        "utf-8"
    )
    ts_str, id_str = raw.split("|", 1)
    # fromisoformat handles "YYYY-MM-DDTHH:MM:SS[.ffffff]" (naive or aware)
    dt = datetime.fromisoformat(ts_str)
    return dt, int(id_str)
