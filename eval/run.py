"""Evaluate helmet detection and dedup on labeled clips in eval/clips/.

Labels: eval/clips/labels.json (format in SPEC.md, "Eval set format").
Prints metrics; exits 0 when all acceptance gates pass, 1 when one fails, 2 when the eval
cannot run (no labels, invalid labels, no pipeline).
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from scoring import (
    DEFAULT_TOLERANCE_S,
    Counts,
    LabelError,
    Pipeline,
    Scenario,
    load_labels,
    score_scenario,
)

CLIPS = Path(__file__).parent / "clips"

# SPEC.md "Acceptance": starting targets, revisit after the M1 baseline. Night/IR is reported only.
DAY_MIN_RECALL = 0.95
DAY_MIN_PRECISION = 0.90
MAX_INCIDENTS_PER_VIOLATION = 1.2
MAX_FALSE_ALARMS_PER_CAMERA_DAY = 1.0


@dataclass(frozen=True)
class Gate:
    name: str
    value: float | None
    limit: float
    at_least: bool  # True: value must be >= limit, False: value must be <= limit
    status: str  # "pass", "fail" or "skipped"


def _gate(name: str, value: float | None, limit: float, at_least: bool) -> Gate:
    if value is None:
        return Gate(name, None, limit, at_least, "fail")  # no data cannot prove the target
    ok = value >= limit if at_least else value <= limit
    return Gate(name, value, limit, at_least, "pass" if ok else "fail")


def evaluate_gates(groups: dict[str, Counts]) -> list[Gate]:
    overall = groups["overall"]
    day = groups.get("condition:day", Counts())
    gates = [
        _gate("day recall", day.recall, DAY_MIN_RECALL, at_least=True),
        _gate("day precision", day.precision, DAY_MIN_PRECISION, at_least=True),
        _gate(
            "incidents per violation",
            overall.incidents_per_violation,
            MAX_INCIDENTS_PER_VIOLATION,
            at_least=False,
        ),
        _gate("suspected merges", float(overall.suspected_merges), 0.0, at_least=False),
    ]
    if overall.camera_seconds >= 86400:
        gates.append(
            _gate(
                "false alarms per camera-day",
                overall.false_alarms_per_camera_day,
                MAX_FALSE_ALARMS_PER_CAMERA_DAY,
                at_least=False,
            )
        )
    else:
        gates.append(
            Gate(
                "false alarms per camera-day",
                None,
                MAX_FALSE_ALARMS_PER_CAMERA_DAY,
                False,
                "skipped",
            )
        )
    return gates


def run_eval(
    scenarios: list[Scenario], pipeline: Pipeline, tolerance_s: float
) -> tuple[dict[str, Counts], dict[str, Counts]]:
    """Run the pipeline on every scenario; return (groups, per-scenario counts)."""
    per_scenario: dict[str, Counts] = {}
    groups: dict[str, Counts] = {"overall": Counts()}
    for scenario in scenarios:
        incidents = pipeline(scenario)
        counts = score_scenario(scenario, incidents, tolerance_s)
        per_scenario[scenario.scenario_id] = counts
        keys = ["overall", f"condition:{scenario.condition}"]
        keys += [f"camera:{cam}" for cam in scenario.clips]
        for key in keys:
            part = counts
            if key.startswith("camera:"):
                part = score_scenario(scenario, incidents, tolerance_s, camera=key[7:])
            groups[key] = groups.get(key, Counts()) + part
    return groups, per_scenario


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def print_report(
    groups: dict[str, Counts], per_scenario: dict[str, Counts], gates: list[Gate]
) -> None:
    print(
        f"{'group':<22}{'viol':>5}{'inc':>5}{'miss':>5}{'dup':>5}{'fa':>4}{'merge':>6}"
        f"{'recall':>8}{'prec':>8}{'inc/viol':>9}"
    )
    for key in sorted(groups, key=lambda k: (k != "overall", k)):
        c = groups[key]
        print(
            f"{key:<22}{c.violations:>5}{c.incidents:>5}{c.missed:>5}{c.duplicates:>5}"
            f"{c.false_alarms:>4}{c.suspected_merges:>6}{_fmt(c.recall):>8}"
            f"{_fmt(c.precision):>8}{_fmt(c.incidents_per_violation):>9}"
        )
    problems = {s: c for s, c in per_scenario.items() if c.missed or c.false_alarms or c.duplicates}
    if problems:
        print("\nscenarios with misses, duplicates or false alarms:")
        for sid, c in problems.items():
            print(
                f"  {sid}: missed={c.missed} duplicates={c.duplicates} false_alarms={c.false_alarms}"
            )
    print("\nacceptance gates:")
    for g in gates:
        op = ">=" if g.at_least else "<="
        print(f"  [{g.status:>7}] {g.name}: {_fmt(g.value)} (need {op} {g.limit})")


def load_pipeline(spec: str) -> Pipeline:
    module_name, _, attr = spec.partition(":")
    if not attr:
        raise LabelError(f"--pipeline must look like module:callable, got {spec!r}")
    return getattr(importlib.import_module(module_name), attr)


def main(argv: Sequence[str] | None = None, pipeline: Pipeline | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--labels", type=Path, default=CLIPS / "labels.json")
    parser.add_argument("--pipeline", help="module:callable taking a Scenario, returning Incidents")
    parser.add_argument(
        "--tolerance",
        type=float,
        default=DEFAULT_TOLERANCE_S,
        help="seconds a violation window is widened when matching incidents",
    )
    parser.add_argument("--out", type=Path, help="write metrics as JSON (for before/after diffs)")
    args = parser.parse_args(argv)

    if not args.labels.exists():
        print(f"No {args.labels} yet. Add labeled clips first (see SPEC.md).")
        return 2
    try:
        scenarios = load_labels(args.labels)
        if pipeline is None and args.pipeline:
            pipeline = load_pipeline(args.pipeline)
    except (LabelError, ImportError, AttributeError) as exc:
        print(f"Cannot run eval: {exc}")
        return 2
    if not scenarios or not any(s.violations for s in scenarios):
        print("Labels contain no scenarios with violations; nothing to measure.")
        return 2
    if pipeline is None:
        print("Labels are valid, but no pipeline is implemented yet (use --pipeline module:fn).")
        return 2

    groups, per_scenario = run_eval(scenarios, pipeline, args.tolerance)
    gates = evaluate_gates(groups)
    print_report(groups, per_scenario, gates)
    if args.out:
        args.out.write_text(
            json.dumps(
                {
                    "version": 1,
                    "tolerance_s": args.tolerance,
                    "groups": {k: c.metrics() for k, c in groups.items()},
                    "scenarios": {k: c.metrics() for k, c in per_scenario.items()},
                    "gates": [g.__dict__ for g in gates],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    return 1 if any(g.status == "fail" for g in gates) else 0


if __name__ == "__main__":
    sys.exit(main())
