# Bonus: the AgentCard, and this failure on the A2A task lifecycle

## The AgentCard

[agent_card.json](../agent_card.json) is what this squad's manager would advertise under A2A:
its skills (`recipe-lookup`, `recipe-scaling`), its input and output modes (plain text in,
text or JSON out), its auth (a bearer token, read-only), and its limits (10 recipe cards,
no nutrition data). An AgentCard is to A2A what `tools/list` is to MCP: the thing another
agent fetches to find out what this one can do before asking it for anything.

## Where the failed case belongs in the lifecycle

An A2A task moves through states: `submitted` → `working` → then `completed`, `failed`,
`canceled`, or it pauses at **`input-required`**.

Our outage run ended with the manager emitting
`UNAVAILABLE: measurer returned HTTP 500` as the cook's answer. Under A2A that is wrong
twice over:

- **It should have ended `failed`**, with the error in the task's status, not in the
  answer field. The cook asked how much sugar; "HTTP 500" is not an answer to that, and a
  calling agent has no way to tell this string apart from a real reply.
- **It should NOT have been `input-required`.** That state is for when the agent needs
  something only the user can supply — if the question had been "scale the pancakes" with
  no amount given, pausing to ask "to how much flour?" would be exactly right. A dead
  worker is our problem, not the cook's, so asking them anything would be passing the buck.

## What A2A buys over a plain REST call to the worker (two lines)

A plain REST call returns a response body and leaves every agent to invent its own
vocabulary for "still working", "need more input", "gave up" — which is precisely how an
error string ends up printed to a cook as if it were a recipe answer.
A2A standardises that vocabulary (task states, artifacts, an AgentCard for discovery and
auth), so a caller can tell a finished answer from a failure from a question without
knowing anything about how the other agent was built.
