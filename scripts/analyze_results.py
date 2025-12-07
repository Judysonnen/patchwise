#!/usr/bin/env python3
"""read a trace.sqlite and print solve rates + tool-call counts per variant.

usage:
    python scripts/analyze_results.py --trace-db trace.sqlite

prints:
  - per-variant solve rate (across all tasks/models/trials)
  - per-(variant, model) breakdown
  - per-task breakdown (which tasks favored which variant)
  - tool-call counts per variant (how chatty each scaffold was)
  - apply_patch error breakdown (what the tool layer caught)

trajectory_id format is `{task}__{variant}__{model}__t{trial}`, parsed back
to attribute each event.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness.trace_store import TraceStore


TID = re.compile(r"^(?P<task>[^_].*?)__(?P<variant>[a-z_]+)__(?P<model>[a-z0-9.\-]+)__t(?P<trial>\d+)$")


def parse_tid(tid: str) -> dict | None:
    m = TID.match(tid)
    return m.groupdict() if m else None


def load_outcomes(trace: TraceStore) -> list[dict]:
    out = []
    for tid in trace.trajectories():
        meta = parse_tid(tid)
        if meta is None:
            continue
        events = list(trace.replay_prefix(tid, up_to_step=10_000))
        outcome = next((e for e in events if e["event_type"] == "outcome"), None)
        n_tool_calls = sum(1 for e in events if e["event_type"] == "tool_result")
        n_apply_patch = sum(
            1 for e in events
            if e["event_type"] == "tool_result" and e["payload"].get("name") == "apply_patch"
        )
        apply_errors = Counter()
        for e in events:
            if e["event_type"] == "tool_result" and e["payload"].get("name") == "apply_patch":
                result = e["payload"].get("result", "")
                if result.startswith("error ("):
                    err_type = result[len("error ("):].split(")")[0]
                    apply_errors[err_type] += 1
        out.append({
            "trajectory_id": tid,
            "task": meta["task"],
            "variant": meta["variant"],
            "model": meta["model"],
            "trial": int(meta["trial"]),
            "success": (outcome["payload"]["success"] if outcome else False),
            "n_tool_calls": n_tool_calls,
            "n_apply_patch_calls": n_apply_patch,
            "apply_errors": dict(apply_errors),
        })
    return out


def fmt_pct(num: int, denom: int) -> str:
    if denom == 0:
        return "  -  "
    return f"{100 * num / denom:5.1f}%"


def print_overall(outcomes: list[dict]) -> None:
    by_variant = defaultdict(list)
    for o in outcomes:
        by_variant[o["variant"]].append(o["success"])
    print("\n## solve rate by variant")
    print(f"{'variant':<20} {'pass':>5} {'total':>5} {'pct':>7}")
    for variant in sorted(by_variant):
        results = by_variant[variant]
        n = sum(results)
        print(f"{variant:<20} {n:>5} {len(results):>5} {fmt_pct(n, len(results)):>7}")


def print_by_variant_model(outcomes: list[dict]) -> None:
    by_vm = defaultdict(list)
    for o in outcomes:
        by_vm[(o["variant"], o["model"])].append(o["success"])
    print("\n## solve rate by (variant, model)")
    print(f"{'variant':<20} {'model':<22} {'pass':>5} {'total':>5} {'pct':>7}")
    for (variant, model) in sorted(by_vm):
        results = by_vm[(variant, model)]
        n = sum(results)
        print(f"{variant:<20} {model:<22} {n:>5} {len(results):>5} {fmt_pct(n, len(results)):>7}")


def print_per_task(outcomes: list[dict]) -> None:
    by_task_variant = defaultdict(lambda: defaultdict(list))
    for o in outcomes:
        by_task_variant[o["task"]][o["variant"]].append(o["success"])
    variants = sorted({o["variant"] for o in outcomes})
    print("\n## solve rate per (task, variant) -- counts pass/total")
    header = f"{'task':<48}"
    for v in variants:
        header += f" {v:>20}"
    print(header)
    for task in sorted(by_task_variant):
        row = f"{task:<48}"
        for v in variants:
            results = by_task_variant[task].get(v, [])
            row += f" {sum(results):>3}/{len(results):<2}              "[:21]
        print(row)


def print_tool_call_counts(outcomes: list[dict]) -> None:
    by_variant = defaultdict(list)
    for o in outcomes:
        by_variant[o["variant"]].append(o["n_tool_calls"])
    print("\n## tool calls per trajectory (mean, by variant)")
    print(f"{'variant':<20} {'mean':>7} {'median':>7} {'max':>5}")
    for variant in sorted(by_variant):
        counts = sorted(by_variant[variant])
        if not counts:
            continue
        mean = sum(counts) / len(counts)
        med = counts[len(counts) // 2]
        print(f"{variant:<20} {mean:>7.1f} {med:>7} {max(counts):>5}")


def print_apply_patch_errors(outcomes: list[dict]) -> None:
    by_variant = defaultdict(Counter)
    for o in outcomes:
        for err, n in o["apply_errors"].items():
            by_variant[o["variant"]][err] += n
    print("\n## apply_patch errors by variant (what the tool layer caught)")
    for variant in sorted(by_variant):
        total = sum(by_variant[variant].values())
        print(f"  {variant} ({total} total):")
        for err, n in by_variant[variant].most_common():
            print(f"    {err:<30} {n}")


def print_multi_file_breakdown(outcomes: list[dict], task_meta: dict[str, dict]) -> None:
    """compare multi-file vs single-file tasks across scaffolds. flagged in
    the resume bullet but with caveat that N is small in the current eval."""
    by_scaffold_class = defaultdict(lambda: defaultdict(list))
    for o in outcomes:
        scaffold = "planner" if "planner" in o["variant"] else "react"
        meta = task_meta.get(o["task"], {})
        bucket = "multi" if meta.get("multi_file") else "single"
        by_scaffold_class[scaffold][bucket].append(o["success"])
    print("\n## scaffold by task type (planner vs react, multi-file vs single)")
    print(f"{'scaffold':<10} {'task type':<10} {'pass':>5} {'total':>5} {'pct':>7}")
    for scaffold in ("react", "planner"):
        for bucket in ("single", "multi"):
            results = by_scaffold_class[scaffold].get(bucket, [])
            print(f"{scaffold:<10} {bucket:<10} {sum(results):>5} {len(results):>5} {fmt_pct(sum(results), len(results)):>7}")


def load_task_meta(tasks_dir: Path) -> dict[str, dict]:
    out = {}
    if not tasks_dir.exists():
        return out
    for d in tasks_dir.iterdir():
        if not d.is_dir() or d.name.startswith("_"):
            continue
        meta_path = d / "meta.json"
        if meta_path.exists():
            out[d.name] = json.loads(meta_path.read_text())
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace-db", default="trace.sqlite")
    ap.add_argument("--tasks-dir", default="harness/tasks")
    args = ap.parse_args()

    db = Path(args.trace_db)
    if not db.exists():
        print(f"trace db not found: {db}")
        return 2

    trace = TraceStore(db)
    outcomes = load_outcomes(trace)
    if not outcomes:
        print("no trajectories with outcomes found in trace db")
        return 1

    task_meta = load_task_meta(Path(args.tasks_dir))

    print(f"loaded {len(outcomes)} trajectories from {db}")
    print_overall(outcomes)
    print_by_variant_model(outcomes)
    print_per_task(outcomes)
    print_tool_call_counts(outcomes)
    print_apply_patch_errors(outcomes)
    print_multi_file_breakdown(outcomes, task_meta)
    return 0


if __name__ == "__main__":
    sys.exit(main())
