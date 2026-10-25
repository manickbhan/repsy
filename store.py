"""Atomic JSON storage for Repsy."""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

DATA_DIR = Path(os.environ.get("REPSY_HOME", Path.home() / ".repsy"))
LOG_PATH, CONFIG_PATH, STATE_PATH = (
    DATA_DIR / "log.json",
    DATA_DIR / "config.json",
    DATA_DIR / "state.json",
)
# Activities are not workout sets. They never count toward the daily set goal.
ACTIVITY_TYPES = [
    {
        "key": "sauna",
        "label": "Sauna",
        "emoji": "🔥",
        "kind": "duration",
        "unit": "minutes",
        "default": 20,
        "color": "#ff7a2a",
    },
    {
        "key": "shaky_chair",
        "label": "Shaky chair",
        "emoji": "🪑",
        "kind": "duration",
        "unit": "minutes",
        "default": 15,
        "color": "#2ad4c8",
        "aka": "vibration plate",
    },
]
DEFAULTS = {
    "sauna_minutes": 20,
    "shaky_chair_minutes": 15,
}
ACTIVITY_ALIASES = {
    "vibration": "shaky_chair",
    "vibration_plate": "shaky_chair",
}
# Peptide / medication protocol items. Doses never count toward the daily set goal.
# Add more peptides in ~/.repsy/config.json under "peptides" (key, label, short,
# emoji, default_amount, unit). Leave default_amount null when the dose is unknown.
PEPTIDE_COLOR = "#3ccf6e"
PEPTIDE_TYPES = [
    {
        "key": "cjc_ipamorelin",
        "label": "CJC-1295/Ipamorelin",
        "short": "CJC/Ipa",
        "emoji": "💉",
        "default_amount": 10,
        "unit": "units",
    },
    {
        "key": "tirzepatide",
        "label": "Tirzepatide",
        "short": "Tirz",
        "emoji": "💉",
        "default_amount": None,
        "unit": "mg",
    },
]
PEPTIDE_ALIASES = {
    "cjc": "cjc_ipamorelin",
    "ipamorelin": "cjc_ipamorelin",
    "cjc_1295": "cjc_ipamorelin",
    "cjc_1295_ipamorelin": "cjc_ipamorelin",
    "cjc/ipamorelin": "cjc_ipamorelin",
    "cjc_ipa": "cjc_ipamorelin",
    "tirz": "tirzepatide",
    "mounjaro": "tirzepatide",
    "zepbound": "tirzepatide",
}
# Protein intake in grams. Does not count toward the set goal.
PROTEIN_CONFIG = {
    "label": "Protein",
    "emoji": "🥤",
    "color": "#f5c542",
    "unit": "g",
    "quick": [
        {"key": "shake", "label": "Protein shake", "emoji": "🥤", "grams": 32},
        {"key": "scoop", "label": "Protein scoop", "emoji": "🥄", "grams": None},
    ],
}
DEFAULT_CONFIG = {
    "goal": 5,
    "active_start": "08:00",
    "active_end": "20:00",
    "nudge_cadence_min": 45,
    "port": 8842,
    "prize": "Set your reward in ~/.repsy/config.json (e.g. 🍣 sushi night)",
    "exercises": [
        {"key": "kettlebells", "label": "Kettlebells", "emoji": "🏋️"},
        {"key": "band", "label": "Band", "emoji": "🎗️"},
        {"key": "squats", "label": "Squats", "emoji": "🦵"},
        {"key": "pushups", "label": "Pushups", "emoji": "💪"},
    ],
    "activities": ACTIVITY_TYPES,
    "defaults": DEFAULTS,
    "peptides": PEPTIDE_TYPES,
    "peptide_color": PEPTIDE_COLOR,
    "protein": PROTEIN_CONFIG,
}


def _atomic_write(path: Path, payload: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(DATA_DIR), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def _read(path: Path, default: dict) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(default) if isinstance(default, dict) else default


def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    cfg.update({k: v for k, v in _read(CONFIG_PATH, {}).items() if v is not None})
    if not cfg.get("activities"):
        cfg["activities"] = ACTIVITY_TYPES
    if not CONFIG_PATH.exists():
        _atomic_write(CONFIG_PATH, cfg)
    return cfg


def resolved_defaults(cfg: dict | None = None) -> dict:
    """Knowable log defaults. Config `defaults` wins, then each activity's `default`."""
    cfg = load_config() if cfg is None else cfg
    out = dict(DEFAULTS)
    stored = cfg.get("defaults") or {}
    by_key = {a.get("key"): a for a in (cfg.get("activities") or ACTIVITY_TYPES)}
    if stored.get("sauna_minutes") is not None:
        out["sauna_minutes"] = int(stored["sauna_minutes"])
    elif (by_key.get("sauna") or {}).get("default") is not None:
        out["sauna_minutes"] = int(by_key["sauna"]["default"])
    if stored.get("shaky_chair_minutes") is not None:
        out["shaky_chair_minutes"] = int(stored["shaky_chair_minutes"])
    elif (by_key.get("shaky_chair") or {}).get("default") is not None:
        out["shaky_chair_minutes"] = int(by_key["shaky_chair"]["default"])
    return out


def activity_types(cfg: dict | None = None) -> list:
    cfg = load_config() if cfg is None else cfg
    defs = resolved_defaults(cfg)
    builtin = {a["key"]: a for a in ACTIVITY_TYPES}
    merged = []
    for item in cfg.get("activities") or ACTIVITY_TYPES:
        if item.get("key") == "cannabis":
            continue
        base = dict(builtin.get(item.get("key"), {}))
        base.update({k: v for k, v in item.items() if v is not None})
        if base.get("kind") == "flag":
            base["kind"] = "puffs"
        key = base.get("key")
        if key == "sauna":
            base["default"] = defs["sauna_minutes"]
            base["unit"] = "minutes"
            base["kind"] = "duration"
        elif key == "shaky_chair":
            base["default"] = defs["shaky_chair_minutes"]
            base["unit"] = "minutes"
            base["kind"] = "duration"
        merged.append(base)
    return merged


def activity_key_set(cfg: dict | None = None) -> set:
    return {a["key"] for a in activity_types(cfg)}


def normalize_activity_key(key: str) -> str:
    norm = (key or "").strip().lower().replace("-", "_").replace(" ", "_")
    return ACTIVITY_ALIASES.get(norm, norm)


def load_log() -> dict:
    return _read(LOG_PATH, {"sets": []})


def save_log(log: dict) -> None:
    _atomic_write(LOG_PATH, log)


def load_state() -> dict:
    return _read(STATE_PATH, {})


def save_state(state: dict) -> None:
    _atomic_write(STATE_PATH, state)


def add_set(exercise_key: str, label: str | None = None, emoji: str = "") -> dict:
    log = load_log()
    log.setdefault("sets", []).append(
        {
            "exercise": exercise_key,
            "label": label or exercise_key,
            "emoji": emoji,
            "ts": datetime.now().isoformat(timespec="seconds"),
        }
    )
    save_log(log)
    return log


def _minutes(value) -> int:
    if isinstance(value, bool) or value is None:
        raise ValueError("Enter a whole number of minutes")
    if isinstance(value, str):
        text = value.strip()
        if not text.isdigit():
            raise ValueError("Enter a whole number of minutes")
        value = int(text)
    elif isinstance(value, float):
        if not value.is_integer():
            raise ValueError("Enter a whole number of minutes")
        value = int(value)
    elif not isinstance(value, int):
        raise ValueError("Enter a whole number of minutes")
    if not 1 <= value <= 300:
        raise ValueError("Minutes must be between 1 and 300")
    return value


def _puffs(value) -> int:
    if isinstance(value, bool) or value is None:
        raise ValueError("Enter a whole number of puffs")
    if isinstance(value, str):
        text = value.strip()
        if not text.isdigit():
            raise ValueError("Enter a whole number of puffs")
        value = int(text)
    elif isinstance(value, float):
        if not value.is_integer():
            raise ValueError("Enter a whole number of puffs")
        value = int(value)
    elif not isinstance(value, int):
        raise ValueError("Enter a whole number of puffs")
    if not 1 <= value <= 100:
        raise ValueError("Puffs must be between 1 and 100")
    return value


def _blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def add_activity(key: str, minutes=None, puffs=None, note: str | None = None, at=None) -> dict:
    """Log an activity. Minutes and puffs fall back to config defaults. Notes are not stored.

    `at` optionally backdates the entry (ISO timestamp, local time if no offset)."""
    key = normalize_activity_key(key)
    spec = next((a for a in activity_types() if a["key"] == key), None)
    if spec is None:
        raise ValueError("Unknown activity")
    defs = resolved_defaults()
    when = parse_at(at)
    entry = {
        "activity": key,
        "label": spec.get("label") or key,
        "emoji": spec.get("emoji", ""),
        "counts_toward_goal": False,
        "ts": when.isoformat(timespec="seconds"),
    }
    if not _blank(at):
        entry["logged_at"] = _now_iso()
    log = load_log()
    acts = log.setdefault("activities", [])
    log.setdefault("sets", [])
    if spec.get("kind") == "duration":
        if _blank(minutes):
            if key == "sauna":
                minutes = defs["sauna_minutes"]
            elif key == "shaky_chair":
                minutes = defs["shaky_chair_minutes"]
            else:
                minutes = spec.get("default")
        entry["minutes"] = _minutes(minutes)
        acts.append(entry)
        save_log(log)
        return log
    if _blank(puffs):
        puffs = spec.get("default") or 1
    n = _puffs(puffs)
    today = when.date().isoformat()
    for existing in acts:
        if existing.get("activity") == key and str(existing.get("ts", ""))[:10] == today:
            existing["puffs"] = int(existing.get("puffs") or 0) + n
            existing.pop("note", None)
            existing["counts_toward_goal"] = False
            existing["label"] = entry["label"]
            existing["emoji"] = entry["emoji"]
            save_log(log)
            return log
    entry["puffs"] = n
    acts.append(entry)
    save_log(log)
    return log


def undo_last_today() -> dict:
    log = load_log()
    sets = log.get("sets", [])
    today = date.today().isoformat()
    for i in range(len(sets) - 1, -1, -1):
        if sets[i]["ts"][:10] == today:
            del sets[i]
            break
    save_log(log)
    return log


def undo_last_activity_today() -> dict:
    """Remove the most recent activity dated today, or backdated (logged) today."""
    log = load_log()
    acts = log.setdefault("activities", [])
    today = date.today().isoformat()
    for i in range(len(acts) - 1, -1, -1):
        if str(acts[i].get("ts", ""))[:10] == today or str(acts[i].get("logged_at", ""))[:10] == today:
            del acts[i]
            break
    save_log(log)
    return log


def sets_on(log: dict, day: date) -> list:
    return [s for s in log.get("sets", []) if s["ts"][:10] == day.isoformat()]


def activities_on(log: dict, day: date) -> list:
    return [a for a in log.get("activities", []) if str(a.get("ts", ""))[:10] == day.isoformat()]


def totals_on(log: dict, day: date) -> dict:
    acts = activities_on(log, day)
    return {
        "sauna_minutes": sum(int(a.get("minutes") or 0) for a in acts if a.get("activity") == "sauna"),
        "shaky_chair_minutes": sum(int(a.get("minutes") or 0) for a in acts if a.get("activity") == "shaky_chair"),
    }


def count_on(log: dict, day: date) -> int:
    return len(sets_on(log, day))


# ---------------------------------------------------------------------------
# Backdating helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def parse_at(at) -> datetime:
    """Parse an optional ISO timestamp. Offsets are converted to local time; naive = local."""
    if _blank(at):
        return datetime.now().replace(microsecond=0)
    if not isinstance(at, str):
        raise ValueError("`at` must be an ISO timestamp string")
    text = at.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError("`at` must be an ISO timestamp like 2026-10-03T22:00:00") from exc
    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)
    if dt > datetime.now() + timedelta(minutes=10):
        raise ValueError("`at` cannot be in the future")
    if dt.year < 2000:
        raise ValueError("`at` is too far in the past")
    return dt.replace(microsecond=0)


def _note(value) -> str | None:
    if _blank(value):
        return None
    return str(value).strip()[:500]


# ---------------------------------------------------------------------------
# Peptide / medication protocol log (log.json "doses"). Never counts toward goal.
# ---------------------------------------------------------------------------


def peptide_color(cfg: dict | None = None) -> str:
    cfg = load_config() if cfg is None else cfg
    return cfg.get("peptide_color") or PEPTIDE_COLOR


def normalize_peptide_key(key: str) -> str:
    norm = (key or "").strip().lower().replace("-", "_").replace(" ", "_")
    return PEPTIDE_ALIASES.get(norm, norm)


def peptide_types(cfg: dict | None = None) -> list:
    cfg = load_config() if cfg is None else cfg
    builtin = {p["key"]: p for p in PEPTIDE_TYPES}
    out = []
    for item in cfg.get("peptides") or PEPTIDE_TYPES:
        if not item.get("key"):
            continue
        base = dict(builtin.get(item["key"], {}))
        base.update(item)  # config wins, including an explicit null default_amount
        base.setdefault("label", base["key"])
        base.setdefault("short", base["label"])
        base.setdefault("emoji", "💉")
        base.setdefault("default_amount", None)
        base.setdefault("unit", None)
        base.setdefault("color", peptide_color(cfg))
        out.append(base)
    return out


def _amount(value):
    if isinstance(value, bool):
        raise ValueError("Dose amount must be a number")
    if isinstance(value, str):
        try:
            value = float(value.strip())
        except ValueError as exc:
            raise ValueError("Dose amount must be a number") from exc
    if not isinstance(value, (int, float)):
        raise ValueError("Dose amount must be a number")
    if not 0 < value <= 100000:
        raise ValueError("Dose amount must be greater than 0")
    value = float(value)
    return int(value) if value.is_integer() else round(value, 4)


_MISSING = object()


def add_dose(name: str, amount=_MISSING, unit=None, note=None, at=None) -> dict:
    """Log a peptide/medication dose. Omitted amount uses the protocol default
    (may be unknown/None); an explicit null/blank amount records the dose as unknown."""
    key = normalize_peptide_key(name)
    spec = next((p for p in peptide_types() if p["key"] == key), None)
    if spec is None:
        raise ValueError(f"Unknown peptide '{name}'. Add it to \"peptides\" in ~/.repsy/config.json")
    when = parse_at(at)
    if amount is _MISSING:
        amount = spec.get("default_amount")
    amount = None if _blank(amount) else _amount(amount)
    unit = None if _blank(unit) else str(unit).strip()[:20]
    if unit is None and amount is not None:
        unit = spec.get("unit")
    entry = {
        "id": uuid.uuid4().hex[:10],
        "peptide": key,
        "label": spec.get("label") or key,
        "emoji": spec.get("emoji", "💉"),
        "amount": amount,
        "unit": unit,
        "counts_toward_goal": False,
        "ts": when.isoformat(timespec="seconds"),
        "logged_at": _now_iso(),
    }
    n = _note(note)
    if n:
        entry["note"] = n
    log = load_log()
    log.setdefault("sets", [])
    log.setdefault("doses", []).append(entry)
    save_log(log)
    return entry


def undo_last_dose(entry_id: str | None = None):
    """Remove a dose by id, else the most recently logged dose (logged or dated today)."""
    log = load_log()
    doses = log.setdefault("doses", [])
    today = date.today().isoformat()
    removed = None
    for i in range(len(doses) - 1, -1, -1):
        d = doses[i]
        if entry_id:
            hit = d.get("id") == entry_id
        else:
            hit = str(d.get("logged_at", ""))[:10] == today or str(d.get("ts", ""))[:10] == today
        if hit:
            removed = doses.pop(i)
            break
    if removed is not None:
        save_log(log)
    return removed


def doses_on(log: dict, day: date) -> list:
    return sorted(
        (d for d in log.get("doses", []) if str(d.get("ts", ""))[:10] == day.isoformat()),
        key=lambda d: d.get("ts", ""),
    )


def fmt_day(dt: datetime, today: date | None = None, with_time: bool = True) -> str:
    today = today or date.today()
    text = f"{dt:%a} {dt.month}/{dt.day}"
    if with_time:
        text += " " + dt.strftime("%I:%M %p").lstrip("0")
    delta = (today - dt.date()).days
    if delta == 0:
        text += " (today)"
    elif delta == 1:
        text += " (yesterday)"
    elif delta > 1:
        text += f" ({delta} days ago)"
    return text


def dose_text(d: dict) -> str:
    if d.get("amount") is None:
        return "dose not recorded"
    unit = d.get("unit") or ""
    return f"{d['amount']:g} {unit}".strip() if isinstance(d["amount"], float) else f"{d['amount']} {unit}".strip()


def last_doses(log: dict, cfg: dict | None = None, today: date | None = None) -> dict:
    today = today or date.today()
    out = {}
    for spec in peptide_types(cfg):
        mine = [d for d in log.get("doses", []) if d.get("peptide") == spec["key"]]
        if not mine:
            out[spec["key"]] = None
            continue
        d = max(mine, key=lambda x: x.get("ts", ""))
        dt = datetime.fromisoformat(d["ts"])
        out[spec["key"]] = {
            "ts": d["ts"],
            "amount": d.get("amount"),
            "unit": d.get("unit"),
            "note": d.get("note"),
            "days_ago": (today - dt.date()).days,
            "display": fmt_day(dt, today),
            "short_display": f"{dt:%a} {dt.month}/{dt.day}",
            "dose": dose_text(d),
        }
    return out


# ---------------------------------------------------------------------------
# Protein intake (log.json "protein"), grams. Never counts toward goal.
# ---------------------------------------------------------------------------


def protein_config(cfg: dict | None = None) -> dict:
    cfg = load_config() if cfg is None else cfg
    out = dict(PROTEIN_CONFIG)
    out.update({k: v for k, v in (cfg.get("protein") or {}).items() if v is not None})
    return out


def _grams(value):
    if isinstance(value, bool):
        raise ValueError("Protein grams must be a number")
    if isinstance(value, str):
        try:
            value = float(value.strip())
        except ValueError as exc:
            raise ValueError("Protein grams must be a number") from exc
    if not isinstance(value, (int, float)):
        raise ValueError("Protein grams must be a number")
    if not 0 < value <= 500:
        raise ValueError("Protein grams must be between 1 and 500")
    value = float(value)
    return int(value) if value.is_integer() else round(value, 1)


def add_protein(grams=None, note=None, at=None, source=None) -> dict:
    """Log protein. grams may be omitted/null if unknown (then a note or source is required)."""
    when = parse_at(at)
    g = None if _blank(grams) else _grams(grams)
    n = _note(note)
    src = None if _blank(source) else str(source).strip().lower()[:40]
    if g is None and not n and not src:
        raise ValueError("Enter protein grams (or a note like '1 scoop' if grams are unknown)")
    entry = {
        "id": uuid.uuid4().hex[:10],
        "grams": g,
        "counts_toward_goal": False,
        "ts": when.isoformat(timespec="seconds"),
        "logged_at": _now_iso(),
    }
    if src:
        entry["source"] = src
    if n:
        entry["note"] = n
    log = load_log()
    log.setdefault("sets", [])
    log.setdefault("protein", []).append(entry)
    save_log(log)
    return entry


def undo_last_protein(entry_id: str | None = None):
    log = load_log()
    items = log.setdefault("protein", [])
    today = date.today().isoformat()
    removed = None
    for i in range(len(items) - 1, -1, -1):
        p = items[i]
        if entry_id:
            hit = p.get("id") == entry_id
        else:
            hit = str(p.get("logged_at", ""))[:10] == today or str(p.get("ts", ""))[:10] == today
        if hit:
            removed = items.pop(i)
            break
    if removed is not None:
        save_log(log)
    return removed


def protein_on(log: dict, day: date) -> list:
    return sorted(
        (p for p in log.get("protein", []) if str(p.get("ts", ""))[:10] == day.isoformat()),
        key=lambda p: p.get("ts", ""),
    )


def protein_total_on(log: dict, day: date) -> dict:
    items = protein_on(log, day)
    total = sum(p["grams"] for p in items if p.get("grams") is not None)
    if isinstance(total, float) and total.is_integer():
        total = int(total)
    return {
        "grams": total,
        "entries": len(items),
        "unknown_entries": sum(1 for p in items if p.get("grams") is None),
    }


# ---------------------------------------------------------------------------
# Morning stack (log.json "morning_stack"): meditation + morning_pages per day.
# Tracking only; never counts toward the set goal. One upserted entry per day.
# ---------------------------------------------------------------------------


def _as_optional_bool(value, field: str):
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in ("true", "yes", "1", "y"):
            return True
        if text in ("false", "no", "0", "n"):
            return False
    raise ValueError(f"{field} must be true or false")


def add_morning_stack(meditation=None, morning_pages=None, at=None, note=None) -> dict:
    """Upsert today's (or `at` day's) morning stack. Pass bools for meditation /
    morning_pages; None leaves an existing field unchanged. At least one flag
    must be provided when creating a new day entry."""
    med = _as_optional_bool(meditation, "meditation")
    pages = _as_optional_bool(morning_pages, "morning_pages")
    when = parse_at(at)
    day = when.date().isoformat()
    n = _note(note)
    log = load_log()
    log.setdefault("sets", [])
    items = log.setdefault("morning_stack", [])
    existing = None
    for entry in items:
        if str(entry.get("ts", ""))[:10] == day:
            existing = entry
            break
    if existing is None:
        if med is None and pages is None:
            raise ValueError("Provide meditation and/or morning_pages (true or false)")
        entry = {
            "id": uuid.uuid4().hex[:10],
            "meditation": med,
            "morning_pages": pages,
            "counts_toward_goal": False,
            "ts": when.isoformat(timespec="seconds"),
            "logged_at": _now_iso(),
        }
        if n:
            entry["note"] = n
        items.append(entry)
        save_log(log)
        return entry
    if med is not None:
        existing["meditation"] = med
    if pages is not None:
        existing["morning_pages"] = pages
    existing["ts"] = when.isoformat(timespec="seconds")
    existing["logged_at"] = _now_iso()
    existing["counts_toward_goal"] = False
    if n:
        existing["note"] = n
    elif "note" in existing and note is not None and _blank(note):
        existing.pop("note", None)
    save_log(log)
    return existing


def undo_morning_stack(entry_id: str | None = None, at=None):
    """Remove a morning-stack entry by id, else the entry for `at`'s day (or today)."""
    log = load_log()
    items = log.setdefault("morning_stack", [])
    if entry_id:
        day = None
    elif not _blank(at):
        day = parse_at(at).date().isoformat()
    else:
        day = date.today().isoformat()
    removed = None
    for i in range(len(items) - 1, -1, -1):
        entry = items[i]
        if entry_id:
            hit = entry.get("id") == entry_id
        else:
            hit = str(entry.get("ts", ""))[:10] == day
        if hit:
            removed = items.pop(i)
            break
    if removed is not None:
        save_log(log)
    return removed


def morning_stack_on(log: dict, day: date):
    """Return the morning-stack entry for `day`, or None."""
    day_s = day.isoformat()
    for entry in log.get("morning_stack", []):
        if str(entry.get("ts", ""))[:10] == day_s:
            return entry
    return None


def morning_stack_summary(entry) -> dict | None:
    """API-shaped summary: {meditation, morning_pages, at[, note, id]}."""
    if not entry:
        return None
    out = {
        "meditation": entry.get("meditation"),
        "morning_pages": entry.get("morning_pages"),
        "at": entry.get("ts"),
    }
    if entry.get("id"):
        out["id"] = entry["id"]
    if entry.get("note"):
        out["note"] = entry["note"]
    return out


def morning_stack_today(log: dict | None = None, today: date | None = None) -> dict | None:
    log = load_log() if log is None else log
    today = today or date.today()
    return morning_stack_summary(morning_stack_on(log, today))
