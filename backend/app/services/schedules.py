from datetime import UTC, datetime, timedelta
from typing import cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter  # type: ignore[import-untyped]


def calculate_next_run(
    schedule_type: str,
    config: dict[str, object],
    timezone_name: str,
    after: datetime | None = None,
) -> datetime | None:
    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown IANA timezone: {timezone_name}") from exc
    now = after or datetime.now(UTC)
    if schedule_type == "once":
        raw = str(config.get("run_at", ""))
        if not raw:
            raise ValueError("once schedule requires run_at")
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=zone)
        utc = parsed.astimezone(UTC)
        return utc if utc > now else None
    if schedule_type == "interval":
        raw_seconds = config.get("seconds", 0)
        if not isinstance(raw_seconds, (str, int)):
            raise ValueError("interval seconds must be an integer")
        seconds = int(raw_seconds)
        if seconds < 60:
            raise ValueError("interval must be at least 60 seconds")
        return now + timedelta(seconds=seconds)
    if schedule_type == "cron":
        expression = str(config.get("expression", ""))
        if not croniter.is_valid(expression):
            raise ValueError("Invalid cron expression")
        local_now = now.astimezone(zone)
        next_run = cast(datetime, croniter(expression, local_now).get_next(datetime))
        return next_run.astimezone(UTC)
    raise ValueError(f"Unknown schedule type: {schedule_type}")
