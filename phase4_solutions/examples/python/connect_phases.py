"""How a Python backend connects Phase 3 -> Phase 4 -> Phase 5 in a few lines.

Run from the phase4_solutions folder:
    python examples/python/connect_phases.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))  # not needed once phase4_solutions is on the path or installed with pip install -e

from phase4.pipeline import run_pipeline, write_pipeline_files  # noqa: E402

# 1. Whatever steps 7 and 8 already produce (here: the example file).
step7_8_output = json.loads((ROOT / "examples/phase3/veloran_step7_8.json").read_text())

# 2. One call. The profile holds client facts steps 7-8 don't have; `expected` adds the scorecard.
result = run_pipeline(step7_8_output, profile="veloran", expected="veloran")

# 3. Hand each part to the phase that needs it.
manager_view = result["manager_view"]        # -> frontend (manager view)
report_sections = result["report"]           # -> step 10 report builder (typed blocks)
report_markdown = result["report_markdown"]  # -> step 10, if the report is Markdown
scorecard = result["scorecard"]              # -> step 10 scorecard

print(manager_view["headline"]["annual_savings"]["display"], "a year;",
      f"{scorecard['matched']} of {scorecard['checks']} numbers match the Veloran report")

# Or write everything to files for teammates who read files:
for path in write_pipeline_files(result, ROOT / "phase4_out"):
    print("wrote", path.relative_to(ROOT))
