"""Phase 4 (step 9) of the Team Tom AI consultant: fixes for each bottleneck.

Takes the bottlenecks from step 7 and their costs from step 8, and returns
AI, software, process and reskilling options for each one, with cost,
savings, payback, a recommended mix and the reasons behind it.

    from phase4 import run_phase4, Phase4Options
    result = run_phase4(step8_output_dict)
"""
from .catalog import Catalog, CatalogError
from .contract import Phase4InputError, normalize_input
from .engine import ENGINE_VERSION, OUTPUT_SCHEMA_VERSION, Phase4Options, run_phase4

__all__ = [
    "run_phase4",
    "Phase4Options",
    "Phase4InputError",
    "Catalog",
    "CatalogError",
    "normalize_input",
    "ENGINE_VERSION",
    "OUTPUT_SCHEMA_VERSION",
]
__version__ = ENGINE_VERSION
