**KEEP the single agent. Do not ship the squad — but not because it lost on quality.**
Naming the bias first: I built the squad this week, which is exactly when sunk cost makes you argue for keeping a thing, so the numbers decide.
Quality is a **wash**: the grader says single **3/10** and squad **2/10**, but reading all 20 answers by hand flips it to 2 and 3 (see manual_adjudication.md), so the one-case gap is noise. Neither arm is shippable at roughly a quarter correct.
Speed is not a wash: the squad's p50 was **69 s** against the single agent's **46 s**, half again as slow, because its three model calls run one after another and nothing here is parallel.
Tokens went the other way: squad **34,748** against single **58,667**, a **0.6x** multiplier — the team was *cheaper*, which is the opposite of the usual warning.
That is a finding about my single agent, not a win for the pattern: it re-sends a growing scratchpad for up to 8 steps, so it is the context-hungry one. Fix that and the squad's advantage disappears.
Cost at hosted prices is $4.41 vs $6.73 per 10,000 questions — far too small a saving to buy a slower answer with no quality gain.
The squad also fails in ways the single agent cannot: the manager emitted a raw `UNAVAILABLE: measurer returned HTTP 500` to the cook, and in an earlier run never delegated the arithmetic at all, so a worker did maths it was forbidden to do and got it wrong.
Multi-agent would earn its place here if the work were genuinely parallel (ten recipes at once), if a specialist needed a different or cheaper model, or if a step needed isolation for permissions — none of which applies to one question about one card.
Decision: keep the single agent, and spend the next week on answer quality rather than topology, because 25% correct is the real problem and no arrangement of agents fixes it.
