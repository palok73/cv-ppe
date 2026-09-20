"""Label loading and incident-level scoring for the eval harness.

Labels live in eval/clips/labels.json (gitignored, see SPEC.md "Eval set format"). A scenario is
one staged recording session with one clip per camera; a violation is one person moving without a
helmet during a time window. Pipelines return `Incident`s and are scored against the violations.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ppe_monitor.types import Incident

LABELS_VERSION = 1
CONDITIONS = ("day", "dusk", "night_ir")
DEFAULT_EPOCH = datetime(2000, 1, 1, tzinfo=UTC)
DEFAULT_TOLERANCE_S = 3.0


class LabelError(ValueError):
    """The labels file is malformed or refers to clips that do not exist."""


@dataclass(frozen=True)
class Violation:
    violation_id: str
    person: str  # anonymous key for one volunteer, only used to tell people apart
    start_s: float
    end_s: float
    cameras: tuple[str, ...]


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    condition: str
    duration_s: float
    epoch: datetime
    clips: dict[str, Path]  # camera_id -> clip file
    violations: tuple[Violation, ...]


Pipeline = Callable[[Scenario], list[Incident]]


@dataclass(frozen=True)
class Counts:
    violations: int = 0
    incidents: int = 0
    matched: int = 0  # violations found by at least one incident
    missed: int = 0
    duplicates: int = 0  # extra incidents for an already-found violation
    false_alarms: int = 0  # incidents that match no violation
    suspected_merges: int = 0  # missed violations that overlap an incident found for another person
    camera_seconds: float = 0.0

    def __add__(self, other: Counts) -> Counts:
        return Counts(*(getattr(self, f) + getattr(other, f) for f in self.__dataclass_fields__))

    @property
    def recall(self) -> float | None:
        return self.matched / self.violations if self.violations else None

    @property
    def precision(self) -> float | None:
        return 1 - self.false_alarms / self.incidents if self.incidents else None

    @property
    def incidents_per_violation(self) -> float | None:
        return (self.matched + self.duplicates) / self.matched if self.matched else None

    @property
    def false_alarms_per_camera_day(self) -> float | None:
        days = self.camera_seconds / 86400
        return self.false_alarms / days if days else None

    def metrics(self) -> dict[str, float | int | None]:
        return {
            "violations": self.violations,
            "incidents": self.incidents,
            "matched": self.matched,
            "missed": self.missed,
            "duplicates": self.duplicates,
            "false_alarms": self.false_alarms,
            "suspected_merges": self.suspected_merges,
            "camera_seconds": self.camera_seconds,
            "recall": self.recall,
            "precision": self.precision,
            "incidents_per_violation": self.incidents_per_violation,
            "false_alarms_per_camera_day": self.false_alarms_per_camera_day,
        }


def load_labels(path: Path) -> list[Scenario]:
    """Parse and validate a labels file; clip paths resolve relative to the file."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LabelError(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(raw, dict) or raw.get("version") != LABELS_VERSION:
        raise LabelError(f"{path}: expected an object with version {LABELS_VERSION}")
    scenarios, seen = [], set()
    for entry in raw.get("scenarios", []):
        scenario = _parse_scenario(entry, path.parent)
        if scenario.scenario_id in seen:
            raise LabelError(f"duplicate scenario id {scenario.scenario_id!r}")
        seen.add(scenario.scenario_id)
        scenarios.append(scenario)
    return scenarios


def _parse_scenario(entry: dict, base: Path) -> Scenario:
    try:
        sid = entry["id"]
        condition = entry["condition"]
        duration_s = float(entry["duration_s"])
        cameras = entry["cameras"]
        epoch = datetime.fromisoformat(entry["epoch"]) if "epoch" in entry else DEFAULT_EPOCH
        raw_violations = entry.get("violations", [])
    except (KeyError, TypeError, ValueError) as exc:
        raise LabelError(f"scenario {entry.get('id', '?')!r}: bad or missing field: {exc}") from exc
    if condition not in CONDITIONS:
        raise LabelError(f"scenario {sid!r}: condition must be one of {CONDITIONS}")
    if epoch.tzinfo is None:
        raise LabelError(f"scenario {sid!r}: epoch must be timezone-aware")
    if not cameras or duration_s <= 0:
        raise LabelError(f"scenario {sid!r}: needs cameras and a positive duration_s")
    clips = {cam: base / name for cam, name in cameras.items()}
    for cam, clip in clips.items():
        if not clip.is_file():
            raise LabelError(f"scenario {sid!r}: clip for {cam!r} not found: {clip}")
    violations, seen = [], set()
    for v in raw_violations:
        violation = _parse_violation(sid, v, tuple(clips), duration_s)
        if violation.violation_id in seen:
            raise LabelError(f"scenario {sid!r}: duplicate violation id {violation.violation_id!r}")
        seen.add(violation.violation_id)
        violations.append(violation)
    return Scenario(sid, condition, duration_s, epoch, clips, tuple(violations))


def _parse_violation(sid: str, v: dict, scenario_cameras: tuple[str, ...], duration_s: float):
    try:
        vid, person = v["id"], v["person"]
        start_s, end_s = float(v["start_s"]), float(v["end_s"])
        cameras = tuple(v.get("cameras", scenario_cameras))
    except (KeyError, TypeError, ValueError) as exc:
        raise LabelError(f"scenario {sid!r}: bad violation {v!r}: {exc}") from exc
    if not 0 <= start_s < end_s <= duration_s:
        raise LabelError(
            f"scenario {sid!r} violation {vid!r}: need 0 <= start_s < end_s <= duration"
        )
    unknown = set(cameras) - set(scenario_cameras)
    if not cameras or unknown:
        raise LabelError(f"scenario {sid!r} violation {vid!r}: unknown cameras {sorted(unknown)}")
    return Violation(vid, person, start_s, end_s, cameras)


def score_scenario(
    scenario: Scenario,
    incidents: list[Incident],
    tolerance_s: float = DEFAULT_TOLERANCE_S,
    camera: str | None = None,
) -> Counts:
    """Match incidents to violations one-to-one and classify what is left over.

    An incident and a violation are candidates when they share a camera and their time windows
    overlap (violation window widened by `tolerance_s`). A maximum one-to-one matching decides
    which incident found which violation, so two people in one view need two incidents. Leftover
    incidents are duplicates (they overlap an already-found violation) or false alarms (they
    overlap nothing). A missed violation that overlaps an incident matched to a different person
    is counted as a suspected merge. With `camera`, only that camera's view is scored.
    """
    violations = [v for v in scenario.violations if camera is None or camera in v.cameras]
    ordered = sorted(
        (i for i in incidents if camera is None or camera in i.camera_ids),
        key=lambda i: (i.first_seen, i.incident_id),
    )
    edges = [_candidates(i, violations, scenario, tolerance_s) for i in ordered]

    found_by: dict[int, int] = {}  # violation index -> incident index

    def assign(i: int, seen: set[int]) -> bool:
        for v in edges[i]:
            if v in seen:
                continue
            seen.add(v)
            if v not in found_by or assign(found_by[v], seen):
                found_by[v] = i
                return True
        return False

    for i in range(len(ordered)):
        assign(i, set())

    matched_incidents = set(found_by.values())
    duplicates = sum(1 for i in range(len(ordered)) if i not in matched_incidents and edges[i])
    false_alarms = sum(1 for i in range(len(ordered)) if not edges[i])
    person_of_incident = {i: violations[v].person for v, i in found_by.items()}
    merges = sum(
        1
        for v, violation in enumerate(violations)
        if v not in found_by
        and any(
            v in edges[i] and person_of_incident.get(i) not in (None, violation.person)
            for i in range(len(ordered))
        )
    )
    return Counts(
        violations=len(violations),
        incidents=len(ordered),
        matched=len(found_by),
        missed=len(violations) - len(found_by),
        duplicates=duplicates,
        false_alarms=false_alarms,
        suspected_merges=merges,
        camera_seconds=scenario.duration_s * (1 if camera else len(scenario.clips)),
    )


def _candidates(
    incident: Incident, violations: list[Violation], scenario: Scenario, tolerance_s: float
) -> list[int]:
    """Indices of violations this incident could be about, best time overlap first."""
    start = (incident.first_seen - scenario.epoch).total_seconds()
    end = (incident.last_seen - scenario.epoch).total_seconds()
    scored = []
    for index, v in enumerate(violations):
        if not set(v.cameras) & set(incident.camera_ids):
            continue
        overlap = min(end, v.end_s + tolerance_s) - max(start, v.start_s - tolerance_s)
        if overlap >= 0:
            scored.append((-overlap, index))
    return [index for _, index in sorted(scored)]
