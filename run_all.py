"""
Run the whole week:

    python run_all.py            the race (both arms) + the outage + all reports
    python run_all.py --reports  rebuild the reports from saved results (instant)

Steps 1 and 2 call the local model and take roughly 30 minutes on a CPU. Everything
is offline and free.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUNS = [
    ("the race: single agent vs kitchen squad, 10 Week-6 cases", ["race.py", "--quiet"]),
    ("the injected outage: the measurer returns HTTP 500", ["race.py", "--failure"]),
]
REPORTS = [
    ("race table, hand-off log, token multiplier", ["make_reports.py"]),
    ("the failure write-up", ["failure_report.py"]),
]

steps = REPORTS if "--reports" in sys.argv else RUNS + REPORTS
for number, (title, command) in enumerate(steps, start=1):
    print("=" * 78)
    print(f"STEP {number}/{len(steps)}: {title}")
    print("=" * 78)
    if subprocess.run([sys.executable, *command], cwd=ROOT).returncode != 0:
        print(f"STEP {number} failed.")
        raise SystemExit(1)
    print()

print("Done. Read RESULTS.md, then results/race_table.md and results/verdict.md.")
