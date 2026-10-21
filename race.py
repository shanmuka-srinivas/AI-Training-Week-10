"""
THE RACE: one agent against a three-agent squad, on the same cases, same grader.

    python race.py                    both arms, 10 cases
    python race.py --arm single       just one arm
    python race.py --failure          the injected worker-outage case only

The rules of a fair race, and why each matters:

  * THE SAME 10 CASES, taken from the Week 6 eval set, unchanged. Writing new
    cases that "suit the squad better" would move the ruler mid-measurement.
  * THE SAME GRADER: evals/checks.py, copied from Week 6 untouched.
  * THE SAME MODEL and the same tools behind MCP for both arms.
  * The squad's specialists get FEWER tools each, on purpose: a narrow brief with
    few tools is the only plausible reason a team would beat one agent.

Four numbers come out for each arm: pass rate, latency (p50 and p99), total
tokens, and cost per question.
"""

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from agent.agent import run_agent  # noqa: E402
from agent.llm import model_name  # noqa: E402
from agent.mcp_client import MCPToolbox  # noqa: E402
from evals.cases import CASES  # noqa: E402
from evals.checks import rule_checks  # noqa: E402
from squad.kitchen_squad import run_squad  # noqa: E402

# The 10 cases, chosen by a rule written down BEFORE anything ran: the first two
# of each rule-checked problem type, in id order. The 11 substitution cases are
# left out because they need the Gemini judge, whose free tier allows 20 calls a
# day — not enough for two arms of fresh answers. Leaving them out keeps the
# grader identical for both arms, which is what the comparison depends on.
SELECTION_RULE = "first two cases of each rule-checked problem type, by id"
TYPES = ["wrong_sentence", "false_refusal", "allergen_yes_no", "must_refuse", "already_working"]


def chosen_cases():
    by_type = {}
    for case in CASES:
        by_type.setdefault(case["type"], []).append(case)
    return [case for t in TYPES for case in by_type[t][:2]]


# For a local model the money cost is zero, so we also price the same token counts
# against a hosted model, to make "cost per question" mean something.
PRICE_IN, PRICE_OUT = 0.10, 0.40   # gemini-2.5-flash-lite, $ per 1M tokens


def as_hosted_cost(input_tokens, output_tokens):
    return input_tokens / 1e6 * PRICE_IN + output_tokens / 1e6 * PRICE_OUT


def grade(case, answer, refused):
    """The Week 6 rule checks, unchanged, used identically for both arms."""
    fake_result = {"answer": answer, "refused": refused, "refusal_reason": "",
                   "citation": "squad" if answer else None, "cited_recipe_id": case.get("recipe"),
                   "context": []}
    checks = rule_checks(case, fake_result)
    return all(ok for _, ok, _ in checks), [{"name": n, "ok": ok, "detail": d} for n, ok, d in checks]


REFUSAL_WORDS = ("cannot", "can't", "could not", "couldn't", "do not contain", "don't contain",
                 "not contain", "no information", "does not say", "doesn't say", "not available",
                 "not in the recipe", "unable", "not provided", "no record")


def looks_like_refusal(answer):
    lowered = answer.lower()
    return any(word in lowered for word in REFUSAL_WORDS)


def run_single(case, toolbox, verbose):
    run = run_agent(case["question"], toolbox, verbose=verbose)
    refused = looks_like_refusal(run.answer)
    passed, checks = grade(case, run.answer, refused)
    return {
        "arm": "single", "case_id": case["id"], "type": case["type"], "question": case["question"],
        "answer": run.answer, "status": run.status, "passed": passed, "checks": checks,
        "seconds": run.seconds, "llm_calls": run.llm_calls,
        "input_tokens": run.input_tokens, "output_tokens": run.output_tokens,
        "tokens": run.input_tokens + run.output_tokens,
        "handoffs": [{"role": "cook -> agent", "detail": f"step {s['n']}", "tokens": None}
                     for s in run.steps],
        "steps": run.steps,
    }


def run_team(case, toolbox, verbose, fail_worker=None, forced_plan=None):
    run = run_squad(case["question"], toolbox, fail_worker=fail_worker,
                    forced_plan=forced_plan, verbose=verbose)
    refused = looks_like_refusal(run.answer)
    passed, checks = grade(case, run.answer, refused)
    return {
        "arm": "squad", "case_id": case["id"], "type": case["type"], "question": case["question"],
        "answer": run.answer, "status": run.status, "passed": passed, "checks": checks,
        "seconds": run.seconds, "llm_calls": run.llm_calls,
        "input_tokens": run.input_tokens, "output_tokens": run.output_tokens,
        "tokens": run.total_tokens,
        "handoffs": run.handoffs, "worker_notes": run.worker_notes,
    }


def summarise(rows):
    seconds = sorted(r["seconds"] for r in rows)
    tokens_in = sum(r["input_tokens"] for r in rows)
    tokens_out = sum(r["output_tokens"] for r in rows)
    return {
        "cases": len(rows),
        "passed": sum(r["passed"] for r in rows),
        "pass_rate": sum(r["passed"] for r in rows) / len(rows),
        "p50_seconds": statistics.median(seconds),
        "p99_seconds": seconds[-1],      # with 10 cases the worst case IS the p99
        "total_seconds": sum(seconds),
        "input_tokens": tokens_in,
        "output_tokens": tokens_out,
        "total_tokens": tokens_in + tokens_out,
        "tokens_per_question": (tokens_in + tokens_out) / len(rows),
        "llm_calls_per_question": sum(r["llm_calls"] for r in rows) / len(rows),
        "hosted_cost_per_question": as_hosted_cost(tokens_in, tokens_out) / len(rows),
        "hosted_cost_total": as_hosted_cost(tokens_in, tokens_out),
        "local_cost_usd": 0.0,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", choices=["single", "squad", "both"], default="both")
    parser.add_argument("--failure", action="store_true", help="run only the injected-outage case")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    verbose = not args.quiet

    cases = chosen_cases()
    with MCPToolbox() as toolbox:
        print(f"Model: {model_name()} | tools: {', '.join(sorted(toolbox.tools))}\n")

        if args.failure:
            # One case that genuinely needs the measurer, with the measurer down.
            case = dict(next(c for c in CASES if c["id"] == "WS-03"),
                        question="I have 600 g of plain flour for the pancakes. How much caster sugar do I need?")
            case["must_contain_any"] = ["48 g"]
            print("INJECTED FAILURE: the measurer returns HTTP 500\n")
            # The manager's own planner does not route to the measurer here (see
            # results/failure_run_attempt1_no_outage.json), so the plan is pinned:
            # otherwise the injected outage never happens and nothing is tested.
            forced = [
                {"worker": "card_reader", "ask": "Find the pancake recipe and report its id and the "
                                                 "weights in its ingredients table."},
                {"worker": "measurer", "ask": "Rescale the Buttermilk Pancakes (R-003) to 600 g of "
                                              "plain flour and report the caster sugar weight."},
            ]
            row = run_team(case, toolbox, verbose, fail_worker="measurer", forced_plan=forced)
            (ROOT / "results").mkdir(exist_ok=True)
            (ROOT / "results" / "failure_run.json").write_text(
                json.dumps(row, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"\nstatus: {row['status']}\nanswer: {row['answer']}")
            print(f"wrote results/failure_run.json")
            return

        rows, started = [], time.perf_counter()
        arms = ["single", "squad"] if args.arm == "both" else [args.arm]
        for arm in arms:
            print("=" * 78)
            print(f"ARM: {arm}")
            print("=" * 78)
            for case in cases:
                print(f"\n{case['id']} ({case['type']}): {case['question']}")
                row = run_single(case, toolbox, verbose) if arm == "single" else run_team(case, toolbox, verbose)
                rows.append(row)
                print(f"   -> {'PASS' if row['passed'] else 'FAIL'} | {row['seconds']:.0f}s | "
                      f"{row['llm_calls']} calls | {row['tokens']} tokens")
                print(f"   answer: {' '.join(row['answer'].split())[:130]}")

    # Re-running one arm must not throw away the other arm's measured results.
    existing = ROOT / "results" / "race_runs.json"
    if existing.exists() and len(arms) == 1:
        kept = [r for r in json.loads(existing.read_text(encoding="utf-8"))["rows"]
                if r["arm"] not in arms]
        rows = kept + rows
    all_arms = sorted({r["arm"] for r in rows}, key=lambda a: a != "single")
    summary = {arm: summarise([r for r in rows if r["arm"] == arm]) for arm in all_arms}
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "race_runs.json").write_text(json.dumps({
        "model": model_name(), "selection_rule": SELECTION_RULE,
        "case_ids": [c["id"] for c in cases], "summary": summary, "rows": rows,
        "worker_max_steps": 5,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n" + "=" * 78)
    for arm, s in summary.items():
        print(f"{arm:7} pass {s['passed']}/{s['cases']} | p50 {s['p50_seconds']:.0f}s p99 {s['p99_seconds']:.0f}s | "
              f"{s['total_tokens']:,} tokens | ${s['hosted_cost_per_question']:.5f}/question (hosted price)")
    if len(summary) == 2:
        multiplier = summary["squad"]["total_tokens"] / summary["single"]["total_tokens"]
        print(f"\ncontext re-send multiplier: {multiplier:.1f}x")
    print(f"\nDone in {time.perf_counter() - started:.0f}s. Wrote results/race_runs.json")


if __name__ == "__main__":
    main()
