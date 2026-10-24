from datetime import date

import pytest

import server
import store
import transfer


@pytest.fixture()
def isolated_data(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "LOG_PATH", tmp_path / "log.json")
    monkeypatch.setattr(store, "CONFIG_PATH", tmp_path / "config.json")
    monkeypatch.setattr(store, "STATE_PATH", tmp_path / "state.json")
    return tmp_path


def test_storage_keeps_goal_categories_separate(isolated_data):
    store.add_set("squats", "Squats", "🦵")
    store.add_activity("sauna", minutes=25)
    store.add_protein(grams="32")
    store.add_morning_stack(meditation=True, morning_pages=False)

    log = store.load_log()
    assert store.count_on(log, date.today()) == 1
    assert store.totals_on(log, date.today())["sauna_minutes"] == 25
    assert store.protein_total_on(log, date.today())["grams"] == 32
    assert store.morning_stack_today(log)["meditation"] is True


def test_web_api_logs_and_rejects_bad_activity(isolated_data):
    client = server.create_app().test_client()

    response = client.post("/log", json={"exercise": "pushups", "label": "Pushups", "emoji": "💪"})
    assert response.status_code == 200
    assert response.get_json()["count"] == 1

    response = client.post("/activity", json={"activity": "sauna", "minutes": 0})
    assert response.status_code == 400
    assert "between 1 and 300" in response.get_json()["error"]


def test_web_api_supports_month_calendar(isolated_data):
    client = server.create_app().test_client()
    response = client.get("/data?month=2026-02")
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["calendar"]["month"] == "2026-02"
    assert len(payload["calendar"]["days"]) >= 28


def test_profile_export_and_import(isolated_data, tmp_path):
    store.add_set("pushups", "Pushups", "💪")
    export_path = tmp_path / "profile.json"
    transfer.export_profile(export_path)

    store.add_set("squats", "Squats", "🦵")
    transfer.import_profile(export_path)

    assert len(store.load_log()["sets"]) == 1
    assert store.load_log()["sets"][0]["label"] == "Pushups"
