from collections import defaultdict
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select

from app.core import fail
from app.planning_models import ItineraryItem, TripDay


def validate_zone(value):
    if value is None:
        return None
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError("請使用有效的 IANA 時區。")
    return value


def local_time(date, clock, zone):
    # fold=0 selects the earlier instant when clocks move backward.
    wall = datetime.combine(date, time.fromisoformat(clock))
    first = wall.replace(tzinfo=ZoneInfo(zone), fold=0)
    if first.astimezone(UTC).astimezone(first.tzinfo).replace(tzinfo=None) != wall:
        return None
    return first


def validate_item_clocks(start_date, day, timezone, start_time, end_time, title):
    if start_date is None:
        return
    date = start_date + timedelta(days=day.day_number - 1)
    zone = timezone or day.timezone
    for clock in (start_time, end_time):
        if clock and local_time(date, clock, zone) is None:
            fail(
                422,
                "nonexistent_local_time",
                f"「{title}」的 {date} {clock} 在 {zone} 因時鐘調整而不存在，請另選時間。",
            )


def validate_trip_clocks(db, trip):
    rows = db.execute(
        select(ItineraryItem, TripDay)
        .join(TripDay, ItineraryItem.day_id == TripDay.id)
        .where(
            ItineraryItem.trip_id == trip.id,
            ItineraryItem.deleted_at.is_(None),
            ItineraryItem.start_time.is_not(None),
        )
    )
    for item, day in rows:
        validate_item_clocks(
            trip.start_date, day, item.timezone, item.start_time, item.end_time, item.title
        )


def annotate_schedule(days, durations):
    """Compute suggestions, never mutate a saved clock, position, or version."""
    intervals = defaultdict(list)
    for day in days:
        travel_date = day["date"]
        zone = day["timezone"]
        # Without a confirmed date, offset/DST conversions cannot be reliably projected.
        clock_date = travel_date or (
            datetime(2000, 1, 1).date() + timedelta(days=day["day_number"] - 1)
        )
        cursor = local_time(clock_date, "09:00", zone)
        cursor_zone = zone
        for item in day["items"]:
            local_zone = item.get("timezone") or zone
            if not travel_date and cursor_zone != local_zone and not item["start_time"]:
                cursor = None
            start = (
                local_time(clock_date, item["start_time"], local_zone)
                if item["start_time"]
                else cursor.astimezone(ZoneInfo(local_zone))
                if cursor
                else None
            )
            item.update(
                suggested_time=None, start_instant=None, local_timezone=local_zone, overlap=False
            )
            end = local_time(clock_date, item["end_time"], local_zone) if item["end_time"] else None
            if travel_date and (
                (item["start_time"] and start is None) or (item["end_time"] and end is None)
            ):
                # Older records may contain a nonexistent wall time. Never fabricate its instant.
                item["clock_note"] = "當地時鐘跳時，請編輯時間。"
                cursor = None
                continue
            if start is None:
                continue
            span = item["duration"] or durations.get(item["place_id"]) or 60
            start_utc = start.astimezone(UTC)
            end_utc = end.astimezone(UTC) if end else start_utc + timedelta(minutes=span)
            item["suggested_time"] = (
                None
                if item["start_time"] or start.date() != clock_date
                else start.strftime("%H:%M")
            )
            if travel_date and (item["start_time"] or item["suggested_time"]):
                item["start_instant"] = start_utc.isoformat()
                if any(
                    t and t.replace(fold=1).utcoffset() != t.utcoffset()
                    for t in (start if item["start_time"] else None, end)
                ):
                    item["clock_note"] = "當地時鐘回撥，重複的小時採第一次出現的時間。"
            if item["start_time"]:
                explicit_end = (
                    end_utc
                    if item["end_time"] or item["duration"]
                    else start_utc + timedelta(minutes=1)
                )
                intervals["absolute" if travel_date else local_zone].append(
                    (start_utc, explicit_end, item)
                )
            cursor = end_utc
            cursor_zone = local_zone
    for group in intervals.values():
        furthest, previous = None, None
        for start, end, item in sorted(group, key=lambda entry: entry[0]):
            if furthest is not None and start < furthest:
                item["overlap"] = previous["overlap"] = True
            if furthest is None or end > furthest:
                furthest, previous = end, item
