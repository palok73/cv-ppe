"""Scoring semantics of the eval harness, on synthetic labels (no footage needed)."""

import json
from datetime import timedelta

import pytest

import run
from ppe_monitor.types import Incident
from scoring import DEFAULT_EPOCH, LabelError, Scenario, Violation, load_labels, score_scenario


def scenario(*violations: Violation, cameras=("cam1", "cam2"), duration_s=100.0) -> Scenario:
    clips = {c: None for c in cameras}
    return Scenario("s1", "day", duration_s, DEFAULT_EPOCH, clips, tuple(violations))


def viol(vid, person, start, end, cameras=("cam1",)) -> Violation:
    return Violation(vid, person, start, end, cameras)


def inc(iid, start, end, cameras=("cam1",)) -> Incident:
    return Incident(
        iid,
        cameras,
        DEFAULT_EPOCH + timedelta(seconds=start),
        DEFAULT_EPOCH + timedelta(seconds=end),
    )


def test_perfect_match():
    c = score_scenario(scenario(viol("v1", "p1", 10, 20)), [inc("i1", 11, 19)])
    assert (c.matched, c.missed, c.duplicates, c.false_alarms) == (1, 0, 0, 0)
    assert c.recall == 1.0 and c.precision == 1.0 and c.incidents_per_violation == 1.0


def test_miss_and_false_alarm():
    c = score_scenario(scenario(viol("v1", "p1", 10, 20)), [inc("i1", 50, 55)])
    assert (c.matched, c.missed, c.false_alarms) == (0, 1, 1)
    assert c.recall == 0.0 and c.precision == 0.0 and c.incidents_per_violation is None


def test_tolerance_widens_the_window():
    s = scenario(viol("v1", "p1", 10, 20))
    assert score_scenario(s, [inc("i1", 22, 23)], tolerance_s=3).matched == 1
    assert score_scenario(s, [inc("i1", 24, 25)], tolerance_s=3).matched == 0


def test_camera_must_overlap():
    c = score_scenario(scenario(viol("v1", "p1", 10, 20)), [inc("i1", 10, 20, cameras=("cam2",))])
    assert (c.matched, c.false_alarms) == (0, 1)


def test_duplicate_is_not_a_false_alarm():
    c = score_scenario(scenario(viol("v1", "p1", 10, 20)), [inc("i1", 10, 15), inc("i2", 16, 20)])
    assert (c.matched, c.duplicates, c.false_alarms) == (1, 1, 0)
    assert c.precision == 1.0 and c.incidents_per_violation == 2.0


def test_two_people_in_one_view_need_two_incidents():
    s = scenario(viol("v1", "p1", 10, 20), viol("v2", "p2", 12, 22))
    both = score_scenario(s, [inc("i1", 10, 20), inc("i2", 12, 22)])
    assert (both.matched, both.duplicates, both.suspected_merges) == (2, 0, 0)


def test_merged_incident_for_two_people_is_flagged():
    s = scenario(viol("v1", "p1", 10, 20), viol("v2", "p2", 12, 22))
    c = score_scenario(s, [inc("i1", 10, 22)])
    assert (c.matched, c.missed, c.suspected_merges) == (1, 1, 1)


def test_missed_violation_of_same_person_is_not_a_merge():
    s = scenario(viol("v1", "p1", 10, 20), viol("v2", "p1", 21, 25))
    c = score_scenario(s, [inc("i1", 10, 25)])
    assert (c.missed, c.suspected_merges) == (1, 0)


def test_cross_camera_incident_matches_violation_seen_on_both():
    s = scenario(viol("v1", "p1", 10, 30, cameras=("cam1", "cam2")))
    c = score_scenario(s, [inc("i1", 10, 30, cameras=("cam1", "cam2"))])
    assert (c.matched, c.duplicates) == (1, 0)
    assert score_scenario(s, [inc("i1", 10, 30, cameras=("cam1", "cam2"))], camera="cam2").matched


def test_per_camera_scoring_ignores_other_cameras():
    s = scenario(viol("v1", "p1", 10, 20, cameras=("cam1",)), viol("v2", "p2", 10, 20, ("cam2",)))
    incidents = [inc("i1", 10, 20, ("cam1",))]
    assert score_scenario(s, incidents, camera="cam1").recall == 1.0
    assert score_scenario(s, incidents, camera="cam2").recall == 0.0


def test_false_alarms_per_camera_day():
    s = scenario(viol("v1", "p1", 10, 20), cameras=("cam1", "cam2"), duration_s=43200)
    c = score_scenario(s, [inc("i1", 10, 20), inc("x", 500, 510)])
    assert c.camera_seconds == 86400 and c.false_alarms_per_camera_day == 1.0


# --- labels loading ---------------------------------------------------------------------


def write_labels(tmp_path, **overrides):
    (tmp_path / "a.mp4").touch()
    entry = {
        "id": "s1",
        "condition": "day",
        "duration_s": 60,
        "cameras": {"cam1": "a.mp4"},
        "violations": [{"id": "v1", "person": "p1", "start_s": 1, "end_s": 5}],
    }
    entry.update(overrides)
    path = tmp_path / "labels.json"
    path.write_text(json.dumps({"version": 1, "scenarios": [entry]}))
    return path


def test_load_labels_defaults_violation_cameras_to_all(tmp_path):
    [s] = load_labels(write_labels(tmp_path))
    assert s.violations[0].cameras == ("cam1",) and s.epoch == DEFAULT_EPOCH
    assert s.clips["cam1"] == tmp_path / "a.mp4"


def test_load_labels_accepts_utf8_bom(tmp_path):
    path = write_labels(tmp_path)
    path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())
    assert load_labels(path)[0].scenario_id == "s1"


@pytest.mark.parametrize(
    "override",
    [
        {"condition": "twilight"},
        {"duration_s": 0},
        {"cameras": {"cam1": "missing.mp4"}},
        {"violations": [{"id": "v", "person": "p", "start_s": 5, "end_s": 1}]},
        {"violations": [{"id": "v", "person": "p", "start_s": 1, "end_s": 99}]},
        {"violations": [{"id": "v", "person": "p", "start_s": 1, "end_s": 5, "cameras": ["x"]}]},
        {"epoch": "2026-01-01T00:00:00"},
    ],
)
def test_load_labels_rejects_bad_input(tmp_path, override):
    with pytest.raises(LabelError):
        load_labels(write_labels(tmp_path, **override))


# --- CLI ----------------------------------------------------------------------------------


def test_main_passes_with_a_perfect_pipeline(tmp_path, capsys):
    labels = write_labels(tmp_path)
    perfect = lambda s: [inc("i1", 1, 5)]
    out = tmp_path / "out.json"
    code = run.main(["--labels", str(labels), "--out", str(out)], pipeline=perfect)
    assert code == 0
    results = json.loads(out.read_text())
    assert results["groups"]["overall"]["recall"] == 1.0
    assert "camera:cam1" in results["groups"] and "condition:day" in results["groups"]
    assert "acceptance gates" in capsys.readouterr().out


def test_main_fails_gates_for_a_blind_pipeline(tmp_path):
    code = run.main(["--labels", str(write_labels(tmp_path))], pipeline=lambda s: [])
    assert code == 1


def test_main_exits_2_without_pipeline_labels_or_violations(tmp_path):
    assert run.main(["--labels", str(tmp_path / "none.json")]) == 2
    assert run.main(["--labels", str(write_labels(tmp_path))]) == 2
    empty = write_labels(tmp_path, violations=[])
    assert run.main(["--labels", str(empty)], pipeline=lambda s: []) == 2
