"""Measured impact engine (workflow steps 4-9). Spec: PHASE_4_PROMPT.md.

Deterministic and standard-library only. It reads a data folder (contract in
engine/contract.py), measures KPIs, detects and sizes bottlenecks, pools
published evidence for each fix, runs a seeded Monte Carlo and writes
outputs/<run_id>/. It feeds the existing step 9 engine (phase4/) through
phase3_handoff.json.
"""

__version__ = "0.1.0"
