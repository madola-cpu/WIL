"""The whole hand-off in one call: Phase 3 output in, everything Phase 5 needs out.

    from phase4.pipeline import run_pipeline, write_pipeline_files
    result = run_pipeline(step7_8_output, profile="veloran", expected="veloran")
    write_pipeline_files(result, "out/phase4")

result keys:
    phase4_input     the validated Phase 4 input built from Phase 3 output
    mapping_report   which Phase 3 field fed which Phase 4 field, and what came from the profile
    phase4_output    the full Phase 4 output (contracts/phase4_output.schema.json)
    manager_view     display-ready data for the frontend (contracts/manager_view.schema.json)
    report           step 10 report sections as typed blocks
    report_markdown  the same sections as Markdown
    scorecard        reference check, when `expected` is given (else None)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .connectors.frontend import manager_view
from .connectors.phase3 import from_phase3
from .connectors.phase5 import render_markdown, report_blocks, scorecard
from .engine import Phase4Options, run_phase4

PIPELINE_VERSION = "phase4-pipeline/1.0"
FILES = {
    "phase4_input": "phase4_input.json",
    "mapping_report": "mapping_report.json",
    "phase4_output": "phase4_output.json",
    "manager_view": "manager_view.json",
    "report": "phase5_report.json",
    "report_markdown": "phase5_report.md",
    "scorecard": "scorecard.json",
}


def run_pipeline(phase3: Any, profile: Union[str, Dict[str, Any], None] = None,
                 mapping: Optional[Dict[str, Any]] = None, expected: Union[str, Dict[str, Any], None] = None,
                 options: Optional[Phase4Options] = None, ai_client: Any = None) -> Dict[str, Any]:
    phase4_input, mapping_report = from_phase3(phase3, profile=profile, mapping=mapping)
    output = run_phase4(phase4_input, options=options, ai_client=ai_client)
    report = report_blocks(output)
    return {
        "pipeline_version": PIPELINE_VERSION,
        "phase4_input": phase4_input,
        "mapping_report": mapping_report,
        "phase4_output": output,
        "manager_view": manager_view(output),
        "report": report,
        "report_markdown": render_markdown(report),
        "scorecard": scorecard(output, expected) if expected is not None else None,
    }


def write_pipeline_files(result: Dict[str, Any], out_dir: Union[str, Path]) -> List[Path]:
    """Write each part of the result to its own file; returns the paths written."""
    folder = Path(out_dir)
    folder.mkdir(parents=True, exist_ok=True)
    written = []
    for key, name in FILES.items():
        value = result.get(key)
        if value is None:
            continue
        path = folder / name
        if isinstance(value, str):
            path.write_text(value, encoding="utf-8")
        else:
            path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written.append(path)
    return written
