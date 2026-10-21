# Reading all 20 answers by hand

The race table uses the Week-6 grader, unchanged, on both arms — that is what makes the
comparison fair, and it is the number that counts. But a grader is a ruler with its own
flaws, so I also read all 20 answers. Three of the ten cases turn out to be scored by an
artifact rather than by quality.

| case | arm | answer | auto | by hand | why they differ |
|---|---|---|---|---|---|
| WS-02 | single | "15 **grams** of garlic are needed" | FAIL | **PASS** | the check looks for "15 g"; "15 grams" does not match it |
| MR-01 | single | "I couldn't finish this task (stopped: step limit (8) reached)" | PASS | **FAIL** | a crash, counted as a refusal because it contains "couldn't" |
| AL-02 | single | "The Buttermilk Pancakes recipe does not contain nuts" | PASS | **FAIL** | the card never says nut-free. This is a false assurance on an allergen question, and the refusal detector read "not contain" as a refusal |
| AL-02 | squad | "No allergens found related to nuts in the recipe card" | FAIL | **PASS** | an honest "the card does not say", which the refusal detector did not recognise |

Everything else was scored correctly by the grader.

| | automatic (the reported number) | after reading by hand |
|---|---|---|
| single | **3/10** | **2/10** |
| squad | **2/10** | **3/10** |

**What this means.** The one-case gap in the race table is inside the noise: reading the
answers flips which arm is ahead. The honest statement is that **quality is
indistinguishable between the two arms**, at a low level that neither should ship: both
are right on about a quarter of these ten questions.

The two glue bugs are mine, in `race.py`:

- `looks_like_refusal()` matches phrases like "not contain" and "couldn't", so it cannot
  tell a refusal from an assertion, or from a crash.
- The Week-6 checks assume the agent's own answer format; "15 grams" versus "15 g" is a
  formatting mismatch, not a wrong answer.

Both affected **the single agent more than the squad**, which is worth saying out loud,
because the headline number is the one that flatters the arm I am recommending.
