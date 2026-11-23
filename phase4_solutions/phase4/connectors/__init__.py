"""Connectors: Phase 3 (steps 7-8) into Phase 4, and Phase 4 out to Phase 5.

    from phase4.connectors import from_phase3, report_blocks, report_markdown, scorecard, manager_view
"""
from .frontend import manager_view
from .phase3 import Phase3MappingError, from_phase3, read_phase3_file
from .phase5 import evidence_index, report_blocks, report_markdown, scorecard

__all__ = [
    "from_phase3",
    "read_phase3_file",
    "Phase3MappingError",
    "report_blocks",
    "report_markdown",
    "scorecard",
    "evidence_index",
    "manager_view",
]
