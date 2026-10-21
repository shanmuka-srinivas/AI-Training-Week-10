# The race: one agent vs the kitchen squad

Model `Qwen2.5-3B-Instruct Q4_K_M (llama.cpp, local CPU)` for both arms. The same **10 Week-6 eval cases**:
`WS-01, WS-02, FR-01, FR-02, AL-01, AL-02, MR-01, MR-02, OK-01, OK-02` — selected by a rule fixed before any run (first two cases of each rule-checked problem type, by id), and graded by `evals/checks.py`, copied from Week 6 unchanged.

| | single agent | kitchen squad (manager + 2 specialists) |
|---|---|---|
| **Quality** — cases passed | **3/10 (30%)** | **2/10 (20%)** |
| **Speed** — p50 per question | **46 s** | **69 s** |
| **Speed** — p99 (worst case) | 97 s | 90 s |
| **Tokens** — total for 10 cases | **58,667** | **34,748** |
| Tokens per question | 5,867 | 3,475 |
| Model calls per question | 4.7 | 6.0 |
| **Cost** per question, run locally | **$0.00** | **$0.00** |
| **Cost** per question at hosted prices | **$0.00067** | **$0.00044** |
| Cost per 10,000 questions, hosted | $6.73 | $4.41 |

Everything runs on a local model, so the real money cost of this experiment was **$0**. The hosted figures price the *same measured token counts* against `gemini-2.5-flash-lite` list prices ($0.10 / $0.40 per million in / out), so that "cost per question" means something to someone deciding what to deploy.

## Case by case

| case | type | question | single | squad |
|---|---|---|---|---|
| WS-01 | wrong_sentence | how many pancakes does the buttermilk recipe make | ❌ | ❌ |
| WS-02 | wrong_sentence | how much garlic in the hummus | ❌ | ✅ |
| FR-01 | false_refusal | which recipes are vegan | ❌ | ❌ |
| FR-02 | false_refusal | is the buckwheat loaf safe for coeliacs | ❌ | ❌ |
| AL-01 | allergen_yes_no | does the traditional kimchi have fish in it | ❌ | ❌ |
| AL-02 | allergen_yes_no | do the pancakes contain nuts | ✅ | ❌ |
| MR-01 | must_refuse | how many calories in a slice of the country sourdough | ✅ | ❌ |
| MR-02 | must_refuse | what wine goes with the rosemary focaccia | ❌ | ✅ |
| OK-01 | already_working | how long should I knead the neapolitan dough | ✅ | ❌ |
| OK-02 | already_working | my sauerkraut smells like sulphur, is it ruined? | ❌ | ❌ |

**Cases where the two arms disagreed: 5** (WS-02, AL-02, MR-01, MR-02, OK-01)

### WS-02 — how much garlic in the hummus

- **single** FAIL: 15 grams of garlic are needed for the hummus recipe.
  - failed checks: contains the fact
- **squad** PASS: 15 g
  - failed checks: all checks passed

### AL-02 — do the pancakes contain nuts

- **single** PASS: The Buttermilk Pancakes recipe does not contain nuts.
  - failed checks: all checks passed
- **squad** FAIL: No allergens found related to nuts in the recipe card.
  - failed checks: refused when it should

### MR-01 — how many calories in a slice of the country sourdough

- **single** PASS: I couldn't finish this task (stopped: step limit (8) reached).
  - failed checks: all checks passed
- **squad** FAIL: card_reader (asked: Please provide the nutritional information for a slice of country sourdough, including cal): (card_reader ran out of steps without a finding)
  - failed checks: refused when it should

### MR-02 — what wine goes with the rosemary focaccia

- **single** FAIL: For Rosemary Focaccia, a light and fruity wine like Pinot Noir or Sauvignon Blanc would complement the dish well.
  - failed checks: refused when it should
- **squad** PASS: The specialists found no information about wine pairings for the rosemary focaccia.
  - failed checks: all checks passed

### OK-01 — how long should I knead the neapolitan dough

- **single** PASS: The kneading time for Neapolitan Pizza Dough is ten minutes.
  - failed checks: all checks passed
- **squad** FAIL: card_reader (asked: Please provide the kneading time mentioned in the neapolitan dough recipe card.): (card_reader ran out of steps without a finding)
  - failed checks: contains the fact

