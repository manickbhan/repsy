"""Pure pace / nudge / weekly-streak logic. No I/O — safe to unit-test."""

from __future__ import annotations

from datetime import date, datetime, timedelta


def parse_hhmm(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def minutes_of(dt: datetime) -> int:
    return dt.hour * 60 + dt.minute


def expected_by_now(now_min: int, start_min: int, end_min: int, goal: int) -> int:
    if now_min <= start_min:
        return 0
    if now_min >= end_min:
        return goal
    frac = (now_min - start_min) / (end_min - start_min)
    return max(0, min(goal, round(goal * frac)))


def in_active_window(now_min: int, start_min: int, end_min: int) -> bool:
    return start_min <= now_min < end_min


def should_nudge(
    *, done, now, start_min, end_min, goal, cadence_min, last_nudge, snooze_until
) -> bool:
    now_min = minutes_of(now)
    if not in_active_window(now_min, start_min, end_min) or done >= goal:
        return False
    # Zero sets always warrant a nudge in the active window. Otherwise only when behind pace.
    if done > 0 and done >= expected_by_now(now_min, start_min, end_min, goal):
        return False
    if snooze_until and now < snooze_until:
        return False
    return not (last_nudge and (now - last_nudge) < timedelta(minutes=cadence_min))


def nudge_message(done, goal, now, end_min) -> tuple[str, str]:
    remaining = goal - done
    hours_left = max(0, end_min - minutes_of(now)) / 60
    if hours_left >= 4:
        sub = f"{done}/{goal} sets — knock one out, plenty of day left 💪"
    elif hours_left >= 2:
        sub = f"{done}/{goal} done — {remaining} to go, don't let it pile up ⏳"
    elif hours_left >= 1:
        sub = f"{remaining} left and it's getting late 👀 squeeze one in now"
    else:
        sub = f"final hour — {remaining} to go to keep the streak 🔥"
    return ("💪 Repsy", sub)


def week_weekdays(today: date) -> list[date]:
    monday = today - timedelta(days=today.weekday())
    return [monday + timedelta(days=i) for i in range(5)]


def iso_week_key(d: date) -> str:
    iso = d.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def is_perfect_week(counts_by_day: dict, today: date, goal: int) -> bool:
    return all(counts_by_day.get(d, 0) >= goal for d in week_weekdays(today))
