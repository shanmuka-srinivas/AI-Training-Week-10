# Week 10, Track B (Recipes & food) — one agent vs a kitchen squad

**Task:** build a manager plus two specialists, race it against the single agent on the
same tests, report quality, speed, tokens and cost, and give an honest verdict.

| Mentor check | Answer |
|---|---|
| Raced on the SAME tests? | **Yes:** the same 10 Week-6 cases, chosen by a rule fixed before any run, graded by `evals/checks.py` copied from Week 6 **byte-identical** |
| All four numbers for both arms? | **Yes** — §2 |
| Verdict backed by the numbers, even if the team lost? | **Yes** — [results/verdict.md](results/verdict.md), 10 lines, sunk-cost named first |
| When would multi-agent be worth it? | §6 |

Everything ran offline on the local Qwen model. Real money cost: **$0**.

---

## 1. The setup

**The squad** ([squad/kitchen_squad.py](squad/kitchen_squad.py)):

| | role | tools |
|---|---|---|
| **manager** | splits the question, then writes the final answer | none |
| **card_reader** | finds recipes, reads a section | `search_recipes`, `get_recipe_section` |
| **measurer** | rescales a recipe to an amount the cook has | `scale_recipe` |

The specialists are deliberately narrow. Giving each one the full toolbox would have
deleted the only plausible reason a team beats one agent, and the race would have
measured nothing.

**Fairness, deliberately:** same model, same MCP tools underneath, same 10 cases, same
grader, both arms run back to back on the same machine.

**The cases:** the first two of each rule-checked Week-6 problem type, by id —
`WS-01, WS-02, FR-01, FR-02, AL-01, AL-02, MR-01, MR-02, OK-01, OK-02`. The 11
substitution cases are excluded because they need the Gemini judge, whose free tier
allows 20 calls a day — not enough for two arms of fresh answers. Excluding them keeps
the grader identical for both arms, which is what the comparison rests on.

---

## 2. The four numbers

| | single agent | kitchen squad |
|---|---|---|
| **Quality** — cases passed | **3/10 (30%)** | **2/10 (20%)** |
| **Speed** — p50 per question | **46 s** | **69 s** |
| **Speed** — p99 (worst case) | 97 s | 90 s |
| **Tokens** — total, 10 cases | **58,667** | **34,748** |
| Tokens per question | 5,867 | 3,475 |
| Model calls per question | 4.7 | 6.0 |
| **Cost** per question (run locally) | **$0.00** | **$0.00** |
| **Cost** per question (hosted prices) | **$0.00067** | **$0.00044** |
| Cost per 10,000 questions (hosted) | $6.73 | $4.41 |

Money is $0 because the model is local, so the same measured token counts are also priced
against `gemini-2.5-flash-lite` list prices ($0.10/$0.40 per million in/out) to make
"cost per question" mean something to someone choosing what to deploy.

Full table: [results/race_table.md](results/race_table.md).

### The quality gap is noise, and I checked

I read all 20 answers. Three of the ten cases are decided by an artifact of my grading
glue rather than by quality ([results/manual_adjudication.md](results/manual_adjudication.md)):

- **WS-02:** the single agent answered "15 **grams** of garlic" — correct, scored FAIL,
  because the check looks for "15 g".
- **MR-01:** the single agent **crashed** ("stopped: step limit reached") and that counted
  as a correct refusal, because my refusal detector sees the word "couldn't".
- **AL-02:** the single agent said "does not contain nuts" — a false assurance the card
  never gives — and **passed**, while the squad's honest "no allergens found ... in the
  recipe card" **failed**.

Scored by hand: **single 2/10, squad 3/10** — the ranking flips. So the honest reading is
**quality is indistinguishable**, at a level neither arm should ship. Both bugs flattered
the single agent, which is the arm I end up recommending, so it matters that I say so.

---

## 3. The context re-send multiplier: 0.6x, not what I expected

**The squad used 0.6x the tokens of the single agent** (34,748 vs 58,667).

The brief warns that teams get expensive because every hand-off re-sends the context. That
is real, and the log shows exactly where it goes
([results/multiplier.md](results/multiplier.md), [results/handoffs.log](results/handoffs.log)):

| hand-off | tokens | share |
|---|---|---|
| **manager → card_reader** | **30,169** | **87%** |
| cook → manager (planning) | 2,492 | 7% |
| workers → manager (synthesis) | 2,087 | 6% |

So 87% of the squad's entire bill is one hand-off: the card_reader's own loop, re-sending
its prompt and its growing observations on every step.

**But the single agent is worse at the same thing.** It carries one conversation for up to
8 steps, re-sending a scratchpad that grows with every tool result. That is why the
multiplier came out below 1. **This is a measurement of my context strategy, not of the
multi-agent pattern** — and it cuts the opposite way to the usual warning. With a
single agent that trimmed its own history, the squad's token advantage would vanish.

---

## 4. The injected failure: what the manager actually did

The `measurer` returns **HTTP 500** on a question that genuinely needs it (rescaling the
pancakes to 600 g of flour, where the answer is 48 g of sugar).

**First attempt: the outage never happened.** The manager's planner never delegated to the
measurer at all — it sent everything to the card_reader, which then did arithmetic it was
explicitly told not to do, and got it wrong (24 g instead of 48 g). Recorded in
[results/failure_run_attempt1_no_outage.json](results/failure_run_attempt1_no_outage.json).
That is a finding in itself: **a specialist boundary that is only a prompt is not a
boundary.**

**Second attempt, with the plan pinned so the dead worker is actually used:**

> **Verdict: DEGRADED.** The manager did not retry, and did not invent a number. It
> emitted the worker's raw error as the cook's answer:
> `UNAVAILABLE: measurer returned HTTP 500 (service unavailable)`

Not a lie, which is the outcome that matters most — but a raw internal error shown to a
cook who asked about sugar. Write-up: [results/failure_case.md](results/failure_case.md).

---

## 5. The verdict

Full text in [results/verdict.md](results/verdict.md) (10 lines, sunk-cost bias named in
line 2). The short version:

**Keep the single agent** — not because the squad lost on quality (it didn't, that's a
wash), but because it is **half again slower** (69 s vs 46 s p50) with no quality gain, and
it fails in ways the single agent cannot. The token saving ($4.41 vs $6.73 per 10,000
questions) is too small to buy that.

And the real finding sits underneath both arms: **about a quarter correct**. No
arrangement of agents fixes an answer-quality problem.

---

## 6. When multi-agent would actually be worth it

Not from the brief — from what this race showed:

1. **When the work is genuinely parallel.** Every one of my hand-offs was sequential, so
   three model calls simply took longer than one. Ten recipes at once would be a different
   story.
2. **When a specialist needs a different model.** A cheap model for lookups and an
   expensive one for judgement is a real saving. One model everywhere, as here, buys
   nothing.
3. **When a step needs isolation.** A worker that must not see the user's private data, or
   must run with narrower permissions, is a safety argument that survives a bad token
   count.
4. **Not for one question about one recipe card**, which is what this app does all day.

---

## 7. What I would not claim

- **10 cases, one run each.** A one-case difference is 10 percentage points. I treated the
  quality gap as noise for exactly that reason.
- **One local model.** A stronger model would lift both arms, and might favour the squad,
  whose workers each solve an easier problem.
- **My first squad design was crippled** (3 steps per worker, so 6 of 10 workers never got
  a turn to report). I found it in the log, raised it to 5, and re-ran. The numbers above
  are the second run; the first is described here rather than quietly dropped.
- **The bonus is partly done:** the AgentCard is written
  ([agent_card.json](agent_card.json)) and the failed case is mapped onto the A2A lifecycle
  ([results/a2a_bonus.md](results/a2a_bonus.md)), but nothing is served over A2A — no HTTP
  endpoint, no real task lifecycle. It is a design, and labelled as one.

## Reproduce

```bash
pip install -r requirements.txt
python run_all.py              # the race + the outage + reports (~30 min, $0)
python run_all.py --reports    # rebuild the reports from saved runs (instant)
```
