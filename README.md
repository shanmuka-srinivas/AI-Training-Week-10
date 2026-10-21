# One Agent vs a Team of Agents: Which Actually Wins?

*Week 10 · Module 5 (MCP, Multi-agent & A2A) · Track B: Recipes & food*

---

## What is this project for?

"Multi-agent" — several AIs working together as a team — is the most hyped idea in AI
right now. The pitch sounds obvious: one AI splits the job up, specialists each do their
bit, and the result is better than one generalist doing everything.

**This project runs the honest experiment instead of believing the pitch.**

We take the recipe agent we already have, build a small team to do the same job, and race
them on the **same questions** with the **same marker**. Then we keep whichever actually
wins — and if the team loses, that's a useful result, not a failure.

Four things get measured, because picking only the flattering one is how teams get sold:

1. **Quality** — how many questions it gets right
2. **Speed** — how long a question takes
3. **Tokens** — how much text the AI has to read and write
4. **Cost** — what that adds up to

We also **break one of the specialists on purpose**, to see whether the manager admits it,
retries, or quietly makes something up.

---

## Input

| What goes in | Details |
|---|---|
| **The single agent** | From Weeks 7–9, unchanged: one AI with all the tools |
| **The kitchen squad** | A manager + 2 specialists, built this week ([squad/kitchen_squad.py](squad/kitchen_squad.py)) |
| **10 test questions** | Taken **unchanged** from the Week 6 eval set |
| **The marker** | `evals/checks.py`, copied from Week 6 **byte-for-byte** |
| **Recipe tools** | Reached over MCP, as built in Week 9 |

> **Why reuse the old questions and marker?** If you write new tests that happen to suit
> your new design, you've moved the ruler mid-measurement and neither number means
> anything. The ruler has to stay still.

---

## Output

| What comes out | Where |
|---|---|
| **The race table** — all four numbers, both arms | [results/race_table.md](results/race_table.md) |
| **Hand-off log** — every AI call with its token count | [results/handoffs.log](results/handoffs.log) |
| **Token multiplier**, traced to one hand-off | [results/multiplier.md](results/multiplier.md) |
| **The broken-specialist test** | [results/failure_case.md](results/failure_case.md) |
| **The verdict** (10 lines) | [results/verdict.md](results/verdict.md) |
| **Reading all 20 answers by hand** | [results/manual_adjudication.md](results/manual_adjudication.md) |
| **A2A bonus**: AgentCard + task lifecycle | [agent_card.json](agent_card.json), [results/a2a_bonus.md](results/a2a_bonus.md) |
| **The write-up** | [RESULTS.md](RESULTS.md) |

### The headline result

| | Single agent | Kitchen squad |
|---|---|---|
| Questions right | **3/10** | 2/10 |
| Typical time per question | **46 s** | 69 s |
| Tokens for all 10 | 58,667 | **34,748** |
| Cost per 10,000 questions (hosted prices) | $6.73 | **$4.41** |

**Verdict: keep the single agent.** Not because the team was worse at answering — that
difference is noise — but because it was **half again slower for no gain**.

---

## What happens between input and output

### The two contenders

**The single agent** (what we already had): one AI, all the tools, one long conversation.

```
cook's question → [ one AI: think → use a tool → think → ... ] → answer
```

**The kitchen squad** (built this week): a manager and two specialists.

```
                    ┌→ card_reader   (finds and reads recipe cards)
cook's question → manager                                        → manager → answer
                    └→ measurer      (rescales recipes)
```

- **manager** — splits the question up, then writes the final answer. **No tools.**
- **card_reader** — only searches and reads cards.
- **measurer** — only rescales recipes.

The specialists get **fewer tools and a shorter brief** on purpose. A narrow job is the
only reason a team should beat a generalist, so handing them the full toolbox would have
made the race pointless.

### Why a team costs more: the hand-off

One agent keeps everything in one conversation. A team can't: every hand-off **re-sends
the context**.

```
manager plans                  → pays for: the question + the manager's instructions
card_reader works              → pays for: its own instructions + its task + every tool result
measurer works                 → pays for: its own instructions + its task again
manager writes the answer      → pays for: the question + everything the workers found
```

So we log **every single AI call with its token count** and add them up. That's how you
can say *"87% of the bill was one hand-off"* instead of guessing.

### Breaking a specialist on purpose

Happy-path demos hide the interesting behaviour. So we made the `measurer` return
**HTTP 500** on a question that needs it, and asked: did the manager **retry**, **degrade**
(answer with what it had and admit the gap), or **lie** (fill the hole itself)?

Lying is the dangerous one, because from outside, a made-up answer looks exactly like a
good one.

### Scoring it fairly

Both arms run back to back, same machine, same model, same tools, same questions, same
marker. The only difference is one agent versus three.

---

## What we found, in plain words

- **The team did not answer better.** 3/10 vs 2/10 by the marker — and when we read all 20
  answers by hand, it flipped to 2 vs 3. The gap is noise. Both arms are poor.
- **The team was slower**, 69 s vs 46 s per question, because its three AI calls happen one
  after another and nothing here can run in parallel.
- **The team was cheaper, which surprised us.** 0.6× the tokens, not the 3–9× the hype
  warns about. That's not a win for teams: it's a finding about *our single agent*, which
  re-sends a growing scratchpad for up to 8 steps. Fix that and the saving disappears.
- **87% of the team's tokens went through one hand-off** (manager → card_reader).
- **A "specialist boundary" made only of instructions is not a boundary.** On the first
  failure test the manager never even called the measurer, so the card_reader did
  arithmetic it was explicitly forbidden to do — and got it wrong (24 g instead of 48 g).
- **When the specialist really did go down, the manager degraded rather than lied** — but it
  pasted a raw `UNAVAILABLE: measurer returned HTTP 500` in front of the cook.
- **The real problem is underneath both designs:** roughly a quarter of answers are right.
  No arrangement of agents fixes that.

---

## Tech stack

| Part | What we used | Why |
|---|---|---|
| Language | **Python 3.13** | |
| The AI model | **Qwen2.5-3B-Instruct, quantised**, via llama.cpp on the CPU | Free, offline, and identical for both arms so the race is fair |
| Tools | The Week 9 **MCP** servers (recipes + ingredients) | Both arms reach tools the same way |
| The single agent | The Week 7–9 loop, unchanged | It's the thing being challenged |
| The squad | Hand-written manager + 2 workers, no framework | CrewAI or AutoGen would hide the hand-off costs, which are the point |
| The marker | `evals/checks.py`, copied from Week 6 byte-for-byte | A ruler you change mid-measurement measures nothing |
| Cost model | Real token counts, priced at `gemini-2.5-flash-lite` list prices | Local runs cost $0, so a hosted price makes the number meaningful |
| A2A | A hand-written **AgentCard**, plus the failure mapped onto the task lifecycle | Design only — nothing is served over HTTP, and that's stated |

**Cost: nothing.** Everything ran on your own machine.

---

## Folder layout

```
squad/kitchen_squad.py    the manager + two specialists, and the hand-off accounting
agent/                    the single agent and the MCP client (unchanged from Week 9)
mcp_servers/              the recipe and ingredient servers (Week 9)
evals/
  cases.py, checks.py     the Week 6 questions and marker, copied unchanged
race.py                   runs both arms on the same cases; --failure runs the outage test
make_reports.py           builds the race table, hand-off log and multiplier
failure_report.py         writes up what the manager did when a worker died
agent_card.json           the A2A AgentCard the squad would advertise
run_all.py                everything, in order
results/                  all the outputs listed above
```

---

## How to run it

```bash
pip install -r requirements.txt

python run_all.py             # the race + the outage test + reports (~30 min, $0)
python run_all.py --reports   # rebuild the reports from saved results (instant)
```

Individual pieces:

```bash
python race.py --arm single    # one arm only
python race.py --failure       # just the broken-specialist test
python make_reports.py         # instant
```

---

## Words you'll see, explained simply

| Term | Meaning |
|---|---|
| **Multi-agent** | Several AIs working together instead of one doing everything |
| **Orchestrator / manager** | The AI that splits the work up and assembles the final answer |
| **Specialist / worker** | An AI with a narrow job and few tools |
| **Hand-off** | Passing work from one AI to another — and paying to re-send the context |
| **Context re-send cost** | Why teams get expensive: the same facts go through the model more than once |
| **p50 / p99** | Typical time (half are faster) and worst case. Clients notice the p99. |
| **A2A** | Agent-to-Agent: a standard for agents to hand work to each other. MCP connects an agent to **tools**; A2A connects it to other **agents**. |
| **AgentCard** | A2A's "here's what I can do" description, like a menu another agent reads first |
| **Task lifecycle** | A2A's standard states for a job: working, completed, failed, or paused for input |
| **Sunk-cost bias** | Wanting to keep something because you spent effort on it. Named out loud in the verdict so it can't quietly drive the decision. |
