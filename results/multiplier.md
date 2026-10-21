# Context re-send multiplier

**The squad used 0.6x the tokens of the single agent** (34,748 vs 58,667 for the same 10 questions).

**The biggest single share is `manager -> card_reader`: 30,169 tokens, 87% of everything the squad spent.**

Where the squad's tokens went, by hand-off:

| hand-off | tokens | share of squad total |
|---|---|---|
| manager -> card_reader | 30,169 | 87% |
| cook -> manager | 2,492 | 7% |
| workers -> manager | 2,087 | 6% |

Every one of those lines is a context re-send. The worker prompts do not know what the
manager knows, and the manager's synthesis call does not know what the workers saw, so
the same facts travel through the model more than once.

