#!/usr/bin/env python3
"""run the 4-variant comparison across tasks, scaffolds, and models.

variants:
    naive_react       - baseline (naive apply_patch + ReAct)
    tolerant_react    - tolerant apply_patch + ReAct       [isolates tool layer]
    naive_planner     - naive apply_patch + planner-executor [isolates scaffold]
    tolerant_planner  - tolerant apply_patch + planner-executor [both]

usage:
    OPENAI_API_KEY=... ANTHROPIC_API_KEY=... \\
        python scripts/run_eval.py --trace-db trace.sqlite

the script discovers whatever tasks exist under harness/tasks/ at run time.
that's by design — early eval runs ship with a small task set; later runs
pick up new fixtures automatically.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# make 'harness' and 'apply_patch' importable when running from the repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness.model_client import AnthropicClient, OpenAIClient
from harness.runner import Runner
from harness.scaffolds.planner_executor import run_planner_executor
from harness.scaffolds.react import run_react
from harness.task import Task, discover_tasks
from harness.trace_store import TraceStore


VARIANTS = {
    "naive_react":      {"apply": "naive",    "scaffold": run_react,             "scaffold_name": "react"},
    "tolerant_react":   {"apply": "tolerant", "scaffold": run_react,             "scaffold_name": "react"},
    "naive_planner":    {"apply": "naive",    "scaffold": run_planner_executor,  "scaffold_name": "planner"},
    "tolerant_planner": {"apply": "tolerant", "scaffold": run_planner_executor,  "scaffold_name": "planner"},
}


def make_model_client(name: str):
    if name.startswith("gpt"):
        return OpenAIClient(name)
    if name.startswith("claude"):
        return AnthropicClient(name)
    raise ValueError(f"don't know which SDK to use for model {name!r}")


def trajectory_id(task: Task, variant: str, model: str, trial: int) -> str:
    return f"{task.slug}__{variant}__{model}__t{trial}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks-dir", default="harness/tasks",
                    help="path to fixture directory")
    ap.add_argument("--task-slugs", default="",
                    help="comma-separated subset of slugs to run (default: all)")
    ap.add_argument("--variants", default=",".join(VARIANTS),
                    help="comma-separated variants to run")
    ap.add_argument("--models", default="gpt-4o-mini,claude-haiku-4-5",
                    help="comma-separated model names")
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--trace-db", default="trace.sqlite")
    # max-steps used to be 25 — got into runaway loops where the model just
    # kept re-reading files. 15 is plenty for these task fixtures.
    ap.add_argument("--max-steps", type=int, default=15)
    ap.add_argument("--dry-run", action="store_true",
                    help="print planned trajectories then exit (no API calls)")
    args = ap.parse_args()

    tasks_dir = Path(args.tasks_dir)
    all_tasks = discover_tasks(tasks_dir)
    if args.task_slugs:
        wanted = set(args.task_slugs.split(","))
        all_tasks = [t for t in all_tasks if t.slug in wanted]
    if not all_tasks:
        print(f"no tasks found under {tasks_dir}")
        return 2

    variants = args.variants.split(",")
    models = args.models.split(",")

    plan = []
    for task in all_tasks:
        for variant in variants:
            for model_name in models:
                for trial in range(args.trials):
                    plan.append((task, variant, model_name, trial))

    print(f"planned {len(plan)} trajectories: "
          f"{len(all_tasks)} tasks x {len(variants)} variants x "
          f"{len(models)} models x {args.trials} trials")

    if args.dry_run:
        for t, v, m, k in plan:
            print(f"  {trajectory_id(t, v, m, k)}")
        return 0

    trace = TraceStore(Path(args.trace_db))

    # build clients lazily so we only fail on missing keys for the models we actually use
    clients: dict[str, object] = {}
    for m in models:
        try:
            clients[m] = make_model_client(m)
        except Exception as e:
            print(f"WARN: could not initialize client for {m}: {e}")
            print("      trajectories using this model will be skipped")
            clients[m] = None

    started = time.time()
    succeeded = failed = skipped = 0
    for task, variant, model_name, trial in plan:
        tid = trajectory_id(task, variant, model_name, trial)
        if clients.get(model_name) is None:
            print(f"SKIP {tid} (no client)")
            skipped += 1
            continue
        v = VARIANTS[variant]
        runner = Runner(
            task=task,
            scaffold=v["scaffold"],
            model=clients[model_name],
            trace=trace,
            apply_patch_variant=v["apply"],
            max_steps=args.max_steps,
        )
        t0 = time.time()
        try:
            result = runner.run(tid)
            mark = "PASS" if result.success else "fail"
            print(f"{mark} {tid}  steps={result.steps_taken}  ({time.time() - t0:.0f}s)")
            if result.success:
                succeeded += 1
            else:
                failed += 1
        except Exception as e:
            print(f"ERR  {tid}  {type(e).__name__}: {e}")
            failed += 1

    elapsed = time.time() - started
    print(f"\ndone in {elapsed:.0f}s. pass={succeeded} fail={failed} skipped={skipped}")
    print(f"trace: {args.trace_db}")
    print(f"analyze with: python scripts/analyze_results.py --trace-db {args.trace_db}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
