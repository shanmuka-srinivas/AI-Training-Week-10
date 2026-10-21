"""
THE KITCHEN SQUAD: one manager, two specialists.

    manager        splits the question up and writes the final answer. No tools.
    card_reader    finds recipes and reads sections. Tools: search_recipes, get_recipe_section
    measurer       weights and scaling. Tool: scale_recipe

The specialists are deliberately NARROW: a short prompt and the fewest tools that
can do their job. That narrowness is the only plausible reason a team would beat
one agent, so handing each worker the full toolbox would throw away the whole
point of the experiment.

WHERE THE COST COMES FROM. A single agent carries one conversation. A team pays
for the same context again at every hand-off: the manager's planning call, then
each worker's own system prompt and task, then the manager's synthesis call with
every worker's findings. Nothing is shared. Every one of those is logged here
with its token count, so the bill can be attributed to a named hand-off rather
than hand-waved at.
"""

import json
import time
from dataclasses import dataclass, field

from agent.llm import LLMError, call_json


class WorkerFailure(Exception):
    """A worker that is down, as opposed to a worker that has nothing to say."""


@dataclass
class SquadRun:
    question: str
    answer: str = ""
    status: str = "finished"
    handoffs: list = field(default_factory=list)   # every model call, with tokens
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    seconds: float = 0.0
    worker_notes: list = field(default_factory=list)

    @property
    def total_tokens(self):
        return self.input_tokens + self.output_tokens


SPECIALISTS = {
    "card_reader": {
        "tools": ["search_recipes", "get_recipe_section"],
        "brief": ("You find recipes and read what the cards say. You do not do arithmetic and you "
                  "do not scale recipes. Find the recipe, read the section that answers the ask, and "
                  "report the exact wording you found."),
    },
    "measurer": {
        "tools": ["scale_recipe"],
        "brief": ("You handle weights. Given a recipe id and an amount the cook has, you rescale the "
                  "recipe and report the weights. You never read method text or allergens."),
    },
}

MANAGER_PLAN = """You are the manager of a two-person kitchen team. Split the cook's question into
work for your specialists. You have exactly these two:

  card_reader - finds recipes and reads a section of a recipe card (ingredients, method,
                allergens, storage, overview). Use for anything the card states in words.
  measurer    - rescales a recipe when the cook has a specific amount of an ingredient.
                Only useful when the question gives an amount in grams or kilos.

Reply with ONE JSON object:
  {{"subtasks": [{{"worker": "card_reader", "ask": "<one specific instruction>"}}]}}

Rules:
- Use only the workers you actually need. Most questions need card_reader alone.
- Each "ask" must be self-contained: the worker cannot see the cook's question.
- At most two subtasks.

The cook asked: {question}"""

WORKER_PROMPT = """You are the {name} on a kitchen team. {brief}

Your tools:

{tools}

Reply with ONE JSON object:
  {{"thought": "<what you need next>", "action": "<tool name, or report>", "args": {{...}}}}
To report back to the manager: {{"thought": "...", "action": "report",
  "args": {{"finding": "<what you found, with exact numbers and wording>"}}}}

Rules:
- Only use the tools above. If none of them can answer, report that plainly.
- Never guess a number. Report what the tool returned.

Your task from the manager: {ask}"""

MANAGER_SYNTH = """You are the manager of a kitchen team. Your specialists have reported back.
Write the final answer for the cook using ONLY what they found.

Reply with ONE JSON object: {{"answer": "<the answer for the cook>"}}

Rules:
- If the findings do not contain the answer, say so plainly. Never fill the gap yourself.
- Keep it short, and include the exact numbers or wording the specialists reported.

The cook asked: {question}

What your specialists reported:
{findings}"""


def _record(run, role, detail, usage):
    run.llm_calls += 1
    run.input_tokens += usage["input_tokens"]
    run.output_tokens += usage["output_tokens"]
    run.cost_usd += usage["cost_usd"]
    run.handoffs.append({
        "role": role, "detail": detail,
        "input_tokens": usage["input_tokens"], "output_tokens": usage["output_tokens"],
        "tokens": usage["input_tokens"] + usage["output_tokens"],
        "seconds": round(usage["seconds"], 2),
    })


def _tool_text(toolbox, allowed):
    blocks = []
    for name, tool in toolbox.tools.items():
        if name not in allowed:
            continue
        schema = (tool["schema"].get("properties") or {})
        args = ", ".join(f"{a}: {s.get('type', 'any')}" for a, s in schema.items())
        blocks.append(f"{name}({args})\n    {tool['description']}")
    return "\n\n".join(blocks)


def run_worker(name, ask, toolbox, run, max_steps=5, fail=False, verbose=False, log=print):
    """
    One specialist: a tiny agent loop with a narrow brief and few tools.

    max_steps=5 after a first run showed 3 was crippling: a worker that needs
    search -> read -> report spends its third call on the tool and never gets a
    turn to report, so 6 of 10 findings came back empty. The single agent gets 8
    steps, so 5 keeps the squad tighter without rigging the race.
    """
    if fail:
        # The injected outage. The worker is up enough to answer the call and down
        # enough to be useless, which is the realistic shape of a service failure.
        raise WorkerFailure(f"{name} returned HTTP 500 (service unavailable)")

    spec = SPECIALISTS[name]
    messages = [{"role": "user", "content": WORKER_PROMPT.format(
        name=name, brief=spec["brief"], tools=_tool_text(toolbox, spec["tools"]), ask=ask)}]

    for step in range(max_steps):
        decision, raw, usage = call_json(messages)
        _record(run, f"manager -> {name}", f"step {step + 1}", usage)
        if not decision:
            messages.append({"role": "user", "content": "That was not valid JSON. Reply with the JSON object only."})
            continue
        action = str(decision.get("action", ""))
        args = decision.get("args") or {}
        if action == "report":
            finding = str(args.get("finding", ""))
            if verbose:
                log(f"      {name} reports: {finding[:150]}")
            return finding
        result = toolbox.call(action, args)
        observation = json.dumps(result, ensure_ascii=False)[:900]
        if verbose:
            log(f"      {name}: {action}({json.dumps(args)}) -> {observation[:120]}")
        messages.append({"role": "assistant", "content": json.dumps(decision)})
        messages.append({"role": "user", "content":
                         f"Result of {action}: {observation}\nNow report back with 'report', "
                         "or take one more step if you truly need it."})

    return f"({name} ran out of steps without a finding)"


def run_squad(question, toolbox, fail_worker=None, forced_plan=None, verbose=False, log=print):
    """
    Manager plans -> specialists work -> manager writes the answer.

    fail_worker: name of a worker to simulate as down, for the failure test.
    forced_plan: pin the delegation instead of letting the manager plan it. Used only
                 by the outage test: the manager's planner does not reliably route to
                 the measurer, and if it never delegates there is no outage to observe.
                 The manager still writes the final answer itself, which is the part
                 being tested.
    """
    run = SquadRun(question=question)
    started = time.perf_counter()

    try:
        # ---- 1. the manager plans -------------------------------------------
        if forced_plan is not None:
            subtasks = list(forced_plan)
        else:
            plan, raw, usage = call_json([{"role": "user", "content": MANAGER_PLAN.format(question=question)}])
            _record(run, "cook -> manager", "plan the work", usage)
            subtasks = (plan or {}).get("subtasks") or []
        if not isinstance(subtasks, list) or not subtasks:
            subtasks = [{"worker": "card_reader", "ask": question}]
        subtasks = [s for s in subtasks if isinstance(s, dict) and s.get("worker") in SPECIALISTS][:2]
        if not subtasks:
            subtasks = [{"worker": "card_reader", "ask": question}]
        if verbose:
            log(f"   manager plan: {[(s['worker'], s['ask'][:60]) for s in subtasks]}")

        # ---- 2. the specialists work ----------------------------------------
        findings = []
        for subtask in subtasks:
            worker = subtask["worker"]
            ask = str(subtask.get("ask") or question)
            try:
                finding = run_worker(worker, ask, toolbox, run,
                                     fail=(worker == fail_worker), verbose=verbose, log=log)
                findings.append({"worker": worker, "ask": ask, "finding": finding})
            except WorkerFailure as outage:
                findings.append({"worker": worker, "ask": ask, "finding": f"UNAVAILABLE: {outage}"})
                run.status = f"degraded: {outage}"
                if verbose:
                    log(f"      {worker} FAILED: {outage}")
        run.worker_notes = findings

        # ---- 3. the manager writes the answer --------------------------------
        findings_text = "\n".join(f"- {f['worker']} (asked: {f['ask'][:90]}): {f['finding']}" for f in findings)
        final, raw, usage = call_json([{"role": "user", "content": MANAGER_SYNTH.format(
            question=question, findings=findings_text)}])
        _record(run, "workers -> manager", "synthesise the answer", usage)
        run.answer = str((final or {}).get("answer", "")).strip()
        if not run.answer:
            run.answer = "I could not produce an answer from what the specialists reported."
            run.status = "stopped: manager produced no answer"
    except LLMError as error:
        run.status = f"error: {error}"
        run.answer = f"I couldn't finish this task ({error})."

    run.seconds = time.perf_counter() - started
    return run
