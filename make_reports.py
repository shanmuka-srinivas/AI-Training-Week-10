"""
Turn results/race_runs.json into the deliverables.

    python make_reports.py

  race_table.md    four metrics x two arms, on the same named cases
  handoffs.log     every hand-off with its token count
  multiplier.md    multi/single token multiplier, attributed to one named hand-off
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
sys.path.insert(0, str(ROOT))


def load():
    path = RESULTS / "race_runs.json"
    if not path.exists():
        raise SystemExit("results/race_runs.json is missing. Run: python race.py")
    return json.loads(path.read_text(encoding="utf-8"))


def race_table(data):
    s, rows = data["summary"], data["rows"]
    single, squad = s.get("single"), s.get("squad")
    lines = [
        "# The race: one agent vs the kitchen squad",
        "",
        f"Model `{data['model']}` for both arms. The same **{len(data['case_ids'])} Week-6 eval cases**:",
        f"`{', '.join(data['case_ids'])}` — selected by a rule fixed before any run "
        f"({data['selection_rule']}), and graded by `evals/checks.py`, copied from Week 6 unchanged.",
        "",
        "| | single agent | kitchen squad (manager + 2 specialists) |",
        "|---|---|---|",
        f"| **Quality** — cases passed | **{single['passed']}/{single['cases']} ({single['pass_rate']:.0%})** | "
        f"**{squad['passed']}/{squad['cases']} ({squad['pass_rate']:.0%})** |",
        f"| **Speed** — p50 per question | **{single['p50_seconds']:.0f} s** | **{squad['p50_seconds']:.0f} s** |",
        f"| **Speed** — p99 (worst case) | {single['p99_seconds']:.0f} s | {squad['p99_seconds']:.0f} s |",
        f"| **Tokens** — total for 10 cases | **{single['total_tokens']:,}** | **{squad['total_tokens']:,}** |",
        f"| Tokens per question | {single['tokens_per_question']:,.0f} | {squad['tokens_per_question']:,.0f} |",
        f"| Model calls per question | {single['llm_calls_per_question']:.1f} | {squad['llm_calls_per_question']:.1f} |",
        f"| **Cost** per question, run locally | **$0.00** | **$0.00** |",
        f"| **Cost** per question at hosted prices | **${single['hosted_cost_per_question']:.5f}** | "
        f"**${squad['hosted_cost_per_question']:.5f}** |",
        f"| Cost per 10,000 questions, hosted | ${single['hosted_cost_per_question'] * 10000:.2f} | "
        f"${squad['hosted_cost_per_question'] * 10000:.2f} |",
        "",
        "Everything runs on a local model, so the real money cost of this experiment was **$0**. "
        "The hosted figures price the *same measured token counts* against "
        "`gemini-2.5-flash-lite` list prices ($0.10 / $0.40 per million in / out), so that "
        "\"cost per question\" means something to someone deciding what to deploy.",
        "",
        "## Case by case",
        "",
        "| case | type | question | single | squad |",
        "|---|---|---|---|---|",
    ]
    by_case = defaultdict(dict)
    for row in rows:
        by_case[row["case_id"]][row["arm"]] = row
    for case_id in data["case_ids"]:
        pair = by_case[case_id]
        one, team = pair.get("single"), pair.get("squad")
        mark = lambda r: ("✅" if r["passed"] else "❌") if r else "–"
        lines.append(f"| {case_id} | {(one or team)['type']} | {(one or team)['question'][:60]} | "
                     f"{mark(one)} | {mark(team)} |")

    disagreements = [cid for cid in data["case_ids"]
                     if by_case[cid].get("single", {}).get("passed") != by_case[cid].get("squad", {}).get("passed")]
    lines += ["", f"**Cases where the two arms disagreed: {len(disagreements)}** "
                  f"({', '.join(disagreements) if disagreements else 'none'})", ""]
    for case_id in disagreements:
        pair = by_case[case_id]
        lines += [f"### {case_id} — {pair['single']['question']}", ""]
        for arm in ("single", "squad"):
            row = pair[arm]
            failed = "; ".join(c["name"] for c in row["checks"] if not c["ok"]) or "all checks passed"
            lines += [f"- **{arm}** {'PASS' if row['passed'] else 'FAIL'}: "
                      f"{' '.join(row['answer'].split())[:170]}",
                      f"  - failed checks: {failed}"]
        lines.append("")
    return "\n".join(lines) + "\n"


def handoff_log(data):
    lines = ["# Hand-off log: every model call, with its token count",
             "",
             "A single agent holds one conversation. A squad pays again at every hand-off: the",
             "manager's plan, each worker's own prompt and task, and the manager's synthesis with",
             "all the findings. Nothing is shared between them. That is what this log prices.",
             ""]
    for arm in ("single", "squad"):
        rows = [r for r in data["rows"] if r["arm"] == arm]
        if not rows:
            continue
        lines += [f"## {arm}", ""]
        if arm == "single":
            lines += [f"One conversation per question, {sum(r['llm_calls'] for r in rows)} model calls in total "
                      f"across {len(rows)} cases, {sum(r['tokens'] for r in rows):,} tokens.",
                      "", "| case | model calls | input tokens | output tokens | total |", "|---|---|---|---|---|"]
            for row in rows:
                lines.append(f"| {row['case_id']} | {row['llm_calls']} | {row['input_tokens']:,} | "
                             f"{row['output_tokens']:,} | {row['tokens']:,} |")
        else:
            lines += ["| case | hand-off | detail | input tokens | output tokens | total |",
                      "|---|---|---|---|---|---|"]
            for row in rows:
                for handoff in row["handoffs"]:
                    lines.append(f"| {row['case_id']} | {handoff['role']} | {handoff['detail']} | "
                                 f"{handoff['input_tokens']:,} | {handoff['output_tokens']:,} | "
                                 f"{handoff['tokens']:,} |")
        lines.append("")
    return "\n".join(lines) + "\n"


def multiplier(data):
    s = data["summary"]
    single_tokens = s["single"]["total_tokens"]
    squad_tokens = s["squad"]["total_tokens"]
    ratio = squad_tokens / single_tokens

    by_role = defaultdict(int)
    for row in data["rows"]:
        if row["arm"] != "squad":
            continue
        for handoff in row["handoffs"]:
            by_role[handoff["role"]] += handoff["tokens"]
    ranked = sorted(by_role.items(), key=lambda kv: -kv[1])
    top_role, top_tokens = ranked[0]
    share = top_tokens / squad_tokens

    lines = [
        "# Context re-send multiplier",
        "",
        f"**The squad used {ratio:.1f}x the tokens of the single agent** "
        f"({squad_tokens:,} vs {single_tokens:,} for the same 10 questions).",
        "",
        f"**The biggest single share is `{top_role}`: {top_tokens:,} tokens, {share:.0%} of everything "
        f"the squad spent.**",
        "",
        "Where the squad's tokens went, by hand-off:",
        "",
        "| hand-off | tokens | share of squad total |",
        "|---|---|---|",
    ]
    lines += [f"| {role} | {tokens:,} | {tokens / squad_tokens:.0%} |" for role, tokens in ranked]
    lines += ["",
              "Every one of those lines is a context re-send. The worker prompts do not know what the",
              "manager knows, and the manager's synthesis call does not know what the workers saw, so",
              "the same facts travel through the model more than once.",
              ""]
    return "\n".join(lines) + "\n"


def main():
    data = load()
    written = []
    for name, builder in (("race_table.md", race_table), ("handoffs.log", handoff_log),
                          ("multiplier.md", multiplier)):
        try:
            (RESULTS / name).write_text(builder(data), encoding="utf-8")
            written.append(name)
        except KeyError as missing:
            print(f"skipped {name}: needs both arms ({missing})")
    print("wrote:", ", ".join(written))


if __name__ == "__main__":
    main()
