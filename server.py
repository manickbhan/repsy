"""Flask UI and local logging API for Repsy."""

from __future__ import annotations

import calendar
from datetime import date
from pathlib import Path

from flask import Flask, jsonify, make_response, request

import pace
import store

TEMPLATE = Path(__file__).parent / "templates" / "dashboard.html"
SET_COLOR = "#2a7fff"


def _parse_month(raw: str | None, today: date) -> tuple[int, int]:
    if raw:
        parts = raw.split("-")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            year, month = int(parts[0]), int(parts[1])
            if 2000 <= year <= 2100 and 1 <= month <= 12:
                return year, month
    return today.year, today.month


def _calendar_payload(log: dict, year: int, month: int, goal: int, today: date) -> dict:
    days = []
    shorts = {p["key"]: p.get("short") or p.get("label") for p in store.peptide_types()}
    for day in calendar.Calendar(firstweekday=6).itermonthdates(year, month):
        sets = store.sets_on(log, day)
        acts = store.activities_on(log, day)
        values = {"sets": len(sets)}
        for spec in store.activity_types():
            key = spec["key"]
            matched = [a for a in acts if a.get("activity") == key]
            if spec.get("kind") == "duration":
                values[key] = sum(int(a.get("minutes") or 0) for a in matched)
            elif spec.get("kind") == "puffs":
                values[key] = sum(int(a.get("puffs") or 0) for a in matched)
            else:
                values[key] = 1 if matched else 0
        doses = store.doses_on(log, day)
        protein = store.protein_total_on(log, day)
        values["peptides"] = len(doses)
        values["protein_g"] = protein["grams"]
        stack = store.morning_stack_on(log, day)
        values["meditation"] = bool(stack.get("meditation")) if stack and stack.get("meditation") is not None else False
        values["morning_pages"] = bool(stack.get("morning_pages")) if stack and stack.get("morning_pages") is not None else False
        values["morning_stack"] = 1 if stack else 0
        days.append(
            {
                "date": day.isoformat(),
                "in_month": day.month == month,
                "is_today": day == today,
                "sets": len(sets),
                "goal_met": len(sets) >= goal,
                "values": values,
                # Peptides and protein are tracked separately; they never count toward the goal.
                "doses": [
                    {"peptide": d.get("peptide"), "short": shorts.get(d.get("peptide"), d.get("label")), "dose": store.dose_text(d)}
                    for d in doses
                ],
                "protein": protein,
                "morning_stack": store.morning_stack_summary(stack),
            }
        )
    return {"month": f"{year:04d}-{month:02d}", "days": days}


def _data_payload(month: str | None = None) -> dict:
    cfg, log, today = store.load_config(), store.load_log(), date.today()
    goal, today_sets = cfg["goal"], store.sets_on(log, today)
    year, mon = _parse_month(month, today)
    counts = {d: store.count_on(log, d) for d in pace.week_weekdays(today)}
    week = [
        {
            "label": label,
            "date": d.isoformat(),
            "count": counts.get(d, 0),
            "done": counts.get(d, 0) >= goal,
            "is_today": d == today,
        }
        for d, label in zip(pace.week_weekdays(today), ["Mon", "Tue", "Wed", "Thu", "Fri"])
    ]
    perfect = pace.is_perfect_week(counts, today, goal)
    return {
        "goal": goal,
        "count": len(today_sets),
        "sets": today_sets,
        "exercises": cfg["exercises"],
        "week": week,
        "perfect_week": perfect,
        "is_saturday": today.weekday() == 5,
        "prize": cfg["prize"],
        "prize_ready": perfect and today.weekday() == 5,
        "activities": store.activities_on(log, today),
        "activity_types": store.activity_types(cfg),
        "defaults": store.resolved_defaults(cfg),
        "today_activities": store.totals_on(log, today),
        "set_color": SET_COLOR,
        # Peptide / medication protocol (never counts toward the set goal)
        "peptide_types": store.peptide_types(cfg),
        "peptide_color": store.peptide_color(cfg),
        "doses": store.doses_on(log, today),
        "last_doses": store.last_doses(log, cfg, today),
        # Protein intake in grams (never counts toward the set goal)
        "protein_config": store.protein_config(cfg),
        "protein": store.protein_on(log, today),
        "protein_today": store.protein_total_on(log, today),
        "protein_total_g": store.protein_total_on(log, today)["grams"],
        # Morning stack: meditation + morning pages (never counts toward set goal)
        "morning_stack": store.morning_stack_today(log, today),
        "calendar": _calendar_payload(log, year, mon, goal, today),
    }


def _log_activity_or_set():
    body = request.get_json(silent=True) or {}
    raw_activity = body.get("activity")
    raw_exercise = body.get("exercise")
    activity_key = store.normalize_activity_key(raw_activity) if raw_activity else ""
    exercise_key = store.normalize_activity_key(raw_exercise) if raw_exercise else ""
    known = store.activity_key_set()
    chosen = ""
    if activity_key:
        chosen = activity_key
    elif exercise_key in known:
        chosen = exercise_key
    if chosen:
        try:
            store.add_activity(
                chosen,
                minutes=body.get("minutes") if "minutes" in body else None,
                puffs=body.get("puffs") if "puffs" in body else None,
                at=body.get("at"),
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
    else:
        key = raw_exercise or "other"
        store.add_set(key, body.get("label") or key, body.get("emoji", ""))
    return jsonify(_data_payload(request.args.get("month")))


def create_app() -> Flask:
    app = Flask(__name__)

    def _page():
        resp = make_response(TEMPLATE.read_text(encoding="utf-8"))
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.get("/")
    def index():
        return _page()

    @app.get("/calendar")
    def calendar_page():
        return _page()

    @app.get("/data")
    def data():
        return jsonify(_data_payload(request.args.get("month")))

    @app.post("/log")
    def log():
        return _log_activity_or_set()

    @app.post("/activity")
    def activity():
        return _log_activity_or_set()

    @app.post("/undo")
    def undo():
        store.undo_last_today()
        return jsonify(_data_payload(request.args.get("month")))

    @app.post("/undo-activity")
    def undo_activity():
        store.undo_last_activity_today()
        return jsonify(_data_payload(request.args.get("month")))

    @app.post("/peptide")
    def peptide():
        body = request.get_json(silent=True) or {}
        name = body.get("name") or body.get("peptide")
        if not name:
            return jsonify({"error": "name is required (e.g. cjc_ipamorelin)"}), 400
        kwargs = {"unit": body.get("unit"), "note": body.get("note"), "at": body.get("at")}
        if "amount" in body:
            kwargs["amount"] = body.get("amount")
        try:
            entry = store.add_dose(name, **kwargs)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        payload = _data_payload(request.args.get("month"))
        payload["logged"] = entry
        return jsonify(payload)

    @app.post("/undo-peptide")
    def undo_peptide():
        body = request.get_json(silent=True) or {}
        removed = store.undo_last_dose(body.get("id"))
        payload = _data_payload(request.args.get("month"))
        payload["removed"] = removed
        return jsonify(payload)

    @app.post("/protein")
    def protein():
        body = request.get_json(silent=True) or {}
        try:
            entry = store.add_protein(
                grams=body.get("grams"), note=body.get("note"), at=body.get("at"), source=body.get("source")
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        payload = _data_payload(request.args.get("month"))
        payload["logged"] = entry
        return jsonify(payload)

    @app.post("/undo-protein")
    def undo_protein():
        body = request.get_json(silent=True) or {}
        removed = store.undo_last_protein(body.get("id"))
        payload = _data_payload(request.args.get("month"))
        payload["removed"] = removed
        return jsonify(payload)

    @app.post("/stack")
    def stack():
        body = request.get_json(silent=True) or {}
        try:
            entry = store.add_morning_stack(
                meditation=body.get("meditation") if "meditation" in body else None,
                morning_pages=body.get("morning_pages") if "morning_pages" in body else None,
                at=body.get("at"),
                note=body.get("note"),
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        payload = _data_payload(request.args.get("month"))
        payload["logged"] = entry
        return jsonify(payload)

    @app.post("/undo-stack")
    def undo_stack():
        body = request.get_json(silent=True) or {}
        removed = store.undo_morning_stack(entry_id=body.get("id"), at=body.get("at"))
        payload = _data_payload(request.args.get("month"))
        payload["removed"] = removed
        return jsonify(payload)

    return app
