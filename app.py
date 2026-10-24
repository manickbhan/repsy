"""Repsy — macOS menu-bar workout-set tracker."""

from __future__ import annotations

import json
import subprocess
import threading
from datetime import date, datetime, timedelta

import rumps

import pace
import store
from server import create_app


def _notify(title: str, subtitle: str, message: str = "", sound: bool = True) -> None:
    """Best-effort macOS notification via osascript (reliable under LaunchAgent)."""
    body = message or subtitle
    try:
        script = (
            f"display notification {json.dumps(body, ensure_ascii=False)} with title {json.dumps(title, ensure_ascii=False)} "
            f"subtitle {json.dumps(subtitle, ensure_ascii=False)}"
        )
        if sound:
            script += ' sound name "Glass"'
        subprocess.run(["osascript", "-e", script], check=False, timeout=5)
    except Exception:
        try:
            rumps.notification(title, subtitle, message, sound=sound)
        except Exception:
            pass



def _activity_menu_title(spec: dict) -> str:
    emoji = spec.get("emoji", "")
    label = spec.get("label", spec.get("key", ""))
    default = spec.get("default")
    if spec.get("kind") == "duration":
        return f"{emoji}  {label} ({default} min)"
    return f"{emoji}  {label} (+{default} puff)"


def _peptide_menu_title(spec: dict) -> str:
    emoji = spec.get("emoji", "💉")
    label = spec.get("label", spec.get("key", ""))
    amount = spec.get("default_amount")
    if amount is None:
        return f"{emoji}  {label} (dose…)"
    return f"{emoji}  {label} ({amount} {spec.get('unit') or ''})".replace(" )", ")")


def _protein_menu_title(quick: dict, cfg_emoji: str) -> str:
    emoji = quick.get("emoji") or cfg_emoji
    grams = quick.get("grams")
    suffix = f" ({grams}g)" if grams is not None else ""
    return f"{emoji}  {quick.get('label', 'Protein')}{suffix}"


def _open_dashboard(cfg: dict) -> None:
    subprocess.run(["open", f"http://127.0.0.1:{cfg['port']}/"], check=False)


class RepsyApp(rumps.App):
    def __init__(self):
        super().__init__("💪", quit_button=None)
        self.cfg = store.load_config()
        self.last_nudge = self.snooze_until = None
        self._build_menu()
        self._update_title()

    def _build_menu(self):
        self.status_item = rumps.MenuItem(f"Today: 0/{self.cfg['goal']}")
        self.activity_item = rumps.MenuItem("Sauna — · Shaky chair — · Cannabis —")
        self.stack_item = rumps.MenuItem("🌅 Morning stack: —")
        self.peptide_item = rumps.MenuItem("💉 Last dose: —")
        self.protein_item = rumps.MenuItem("🥤 Protein today: 0g")
        items = [self.status_item, self.activity_item, self.stack_item, self.peptide_item, self.protein_item, rumps.separator]
        for ex in self.cfg["exercises"]:
            items.append(
                rumps.MenuItem(
                    f"{ex['emoji']}  {ex['label']}", callback=self._make_logger(ex)
                )
            )
        items += [
            rumps.MenuItem("➕  Other…", callback=self._log_other),
            rumps.separator,
        ]
        for spec in store.activity_types(self.cfg):
            items.append(
                rumps.MenuItem(
                    _activity_menu_title(spec),
                    callback=self._make_activity_logger(spec),
                )
            )
        items.append(rumps.separator)
        for spec in store.peptide_types(self.cfg):
            items.append(
                rumps.MenuItem(_peptide_menu_title(spec), callback=self._make_peptide_logger(spec))
            )
        pcfg = store.protein_config(self.cfg)
        for quick in pcfg.get("quick") or []:
            items.append(
                rumps.MenuItem(
                    _protein_menu_title(quick, pcfg.get("emoji", "🥤")),
                    callback=self._make_protein_logger(quick),
                )
            )
        items += [
            rumps.MenuItem("🥤  Protein (grams)…", callback=self._log_protein_custom),
            rumps.MenuItem("Undo last dose", callback=self._undo_dose),
            rumps.MenuItem("Undo last protein", callback=self._undo_protein),
            rumps.separator,
            rumps.MenuItem("🧘  Meditation yes", callback=self._stack_med_yes),
            rumps.MenuItem("🧘  Meditation no", callback=self._stack_med_no),
            rumps.MenuItem("📝  Morning pages yes", callback=self._stack_pages_yes),
            rumps.MenuItem("📝  Morning pages no", callback=self._stack_pages_no),
            rumps.MenuItem("Undo morning stack", callback=self._undo_stack),
        ]
        items += [
            rumps.separator,
            rumps.MenuItem("Open dashboard ↗", callback=self._open),
            rumps.MenuItem("Open calendar ↗", callback=self._open_calendar),
            rumps.MenuItem("Undo last set", callback=self._undo),
            rumps.MenuItem("Snooze nudges 30m", callback=self._snooze),
            rumps.separator,
            rumps.MenuItem("Quit Repsy", callback=rumps.quit_application),
        ]
        self.menu = items

    def _make_logger(self, ex):
        def cb(_):
            store.add_set(ex["key"], ex["label"], ex["emoji"])
            self._update_title()
            self._celebrate_if_done()

        return cb

    def _log_other(self, _):
        response = rumps.Window(
            title="Log a set",
            message="What did you do?",
            default_text="Other",
            ok="Log",
            cancel="Cancel",
            dimensions=(220, 24),
        ).run()
        if getattr(response, "clicked", 0) and response.text.strip():
            store.add_set("other", response.text.strip(), "✅")
            self._update_title()
            self._celebrate_if_done()

    def _make_activity_logger(self, spec):
        def cb(_):
            try:
                if spec.get("kind") == "duration":
                    store.add_activity(spec["key"], minutes=spec.get("default"))
                else:
                    store.add_activity(spec["key"], puffs=spec.get("default") or 1)
            except ValueError as exc:
                _notify("💪 Repsy", "Not logged", str(exc), sound=False)
                return
            self._update_title()

        return cb

    def _make_peptide_logger(self, spec):
        def cb(_):
            try:
                if spec.get("default_amount") is None:
                    unit = spec.get("unit") or ""
                    response = rumps.Window(
                        title=f"Log {spec.get('label')}",
                        message=f"Dose amount{(' in ' + unit) if unit else ''} (leave blank if unknown)",
                        default_text="",
                        ok="Log",
                        cancel="Cancel",
                        dimensions=(220, 24),
                    ).run()
                    if not getattr(response, "clicked", 0):
                        return
                    text = response.text.strip()
                    store.add_dose(spec["key"], amount=text or None, unit=unit if text else None)
                else:
                    store.add_dose(spec["key"])
            except ValueError as exc:
                _notify("💪 Repsy", "Not logged", str(exc), sound=False)
                return
            self._update_title()

        return cb

    def _make_protein_logger(self, quick):
        def cb(_):
            try:
                note = None if quick.get("grams") is not None else f"1 {quick.get('key') or 'serving'}"
                store.add_protein(grams=quick.get("grams"), note=note, source=quick.get("key"))
            except ValueError as exc:
                _notify("💪 Repsy", "Not logged", str(exc), sound=False)
                return
            self._update_title()

        return cb

    def _log_protein_custom(self, _):
        response = rumps.Window(
            title="Log protein",
            message="Grams of protein",
            default_text="",
            ok="Log",
            cancel="Cancel",
            dimensions=(220, 24),
        ).run()
        if getattr(response, "clicked", 0) and response.text.strip():
            try:
                store.add_protein(grams=response.text.strip())
            except ValueError as exc:
                _notify("💪 Repsy", "Not logged", str(exc), sound=False)
                return
            self._update_title()

    def _undo_dose(self, _):
        store.undo_last_dose()
        self._update_title()

    def _undo_protein(self, _):
        store.undo_last_protein()
        self._update_title()

    def _log_stack(self, **kwargs):
        try:
            store.add_morning_stack(**kwargs)
        except ValueError as exc:
            _notify("💪 Repsy", "Not logged", str(exc), sound=False)
            return
        self._update_title()

    def _stack_med_yes(self, _):
        self._log_stack(meditation=True)

    def _stack_med_no(self, _):
        self._log_stack(meditation=False)

    def _stack_pages_yes(self, _):
        self._log_stack(morning_pages=True)

    def _stack_pages_no(self, _):
        self._log_stack(morning_pages=False)

    def _undo_stack(self, _):
        store.undo_morning_stack()
        self._update_title()

    def _open(self, _):
        _open_dashboard(self.cfg)

    def _open_calendar(self, _):
        subprocess.run(["open", f"http://127.0.0.1:{self.cfg['port']}/calendar"], check=False)

    def _undo(self, _):
        store.undo_last_today()
        self._update_title()

    def _snooze(self, _):
        self.snooze_until = datetime.now() + timedelta(minutes=30)
        _notify("💪 Repsy", "Snoozed", "No nudges for 30 minutes.", sound=False)

    def _count_today(self):
        return store.count_on(store.load_log(), date.today())

    def _update_title(self):
        n, goal = self._count_today(), self.cfg["goal"]
        if n >= goal:
            self.title = f"💪 {n}/{goal} ✅"
        else:
            self.title = (
                f"💪 {n}/{goal} ⏰"
                if n
                < pace.expected_by_now(
                    pace.minutes_of(datetime.now()),
                    pace.parse_hhmm(self.cfg["active_start"]),
                    pace.parse_hhmm(self.cfg["active_end"]),
                    goal,
                )
                else f"💪 {n}/{goal}"
            )
        self.status_item.title = f"Today: {n}/{goal}"
        log = store.load_log()
        totals = store.totals_on(log, date.today())
        self.activity_item.title = (
            f"🔥 Sauna {totals['sauna_minutes']}m · "
            f"🪑 Shaky chair {totals['shaky_chair_minutes']}m · "
            f"🌿 Cannabis {totals['cannabis_puffs']} puffs"
        )
        try:
            last = store.last_doses(log, self.cfg)
            parts = []
            for spec in store.peptide_types(self.cfg):
                info = last.get(spec["key"])
                when = info["short_display"] if info else "never"
                parts.append(f"{spec.get('short') or spec.get('label')} {when}")
            self.peptide_item.title = "💉 Last: " + " · ".join(parts) if parts else "💉 No peptides configured"
            prot = store.protein_total_on(log, date.today())
            extra = f" (+{prot['unknown_entries']} unweighed)" if prot["unknown_entries"] else ""
            self.protein_item.title = f"🥤 Protein today: {prot['grams']}g{extra}"
            stack = store.morning_stack_today(log)
            if stack:
                med = "yes" if stack.get("meditation") else ("no" if stack.get("meditation") is False else "—")
                pages = "yes" if stack.get("morning_pages") else ("no" if stack.get("morning_pages") is False else "—")
                self.stack_item.title = f"🌅 Stack: med {med} · pages {pages}"
            else:
                self.stack_item.title = "🌅 Morning stack: not logged"
        except Exception as exc:  # never let tracking display break the set counter
            self.peptide_item.title = f"💉 Peptides: error ({exc})"

    def _celebrate_if_done(self):
        n = self._count_today()
        if n == self.cfg["goal"]:
            _notify("💪 Repsy", "Goal hit!", f"{n}/{n} sets done today. 🔥")

    @rumps.timer(60)
    def _tick(self, _):
        self.cfg = store.load_config()
        self._update_title()
        now = datetime.now()
        self._maybe_nudge(now)

    def _maybe_nudge(self, now):
        n = self._count_today()
        start, end = (
            pace.parse_hhmm(self.cfg["active_start"]),
            pace.parse_hhmm(self.cfg["active_end"]),
        )
        if pace.should_nudge(
            done=n,
            now=now,
            start_min=start,
            end_min=end,
            goal=self.cfg["goal"],
            cadence_min=self.cfg["nudge_cadence_min"],
            last_nudge=self.last_nudge,
            snooze_until=self.snooze_until,
        ):
            title, sub = pace.nudge_message(n, self.cfg["goal"], now, end)
            _notify(title, sub, "Click the menu bar to log a set.")
            self.last_nudge = now


def _start_server():
    app, cfg = create_app(), store.load_config()
    app.run(host="127.0.0.1", port=cfg["port"], threaded=True, use_reloader=False)


def main():
    store.load_config()
    threading.Thread(target=_start_server, daemon=True).start()
    RepsyApp().run()


if __name__ == "__main__":
    main()
