#!/usr/bin/env python3
"""Generates the frozen eval/trial_seeds.json manifest (BUILD_PLAN.md
section 11 and section 13). Run once, before the confirmatory batch
begins; the output is committed and never regenerated for the same
confirmatory claim (freeze contract, section 13). A future algorithm
correction requires a newly generated, previously unused manifest under a
new `eval-frozen-vN` tag, not a rerun of this script over the same file.

Deterministic and reproducible: everything below is a pure function of the
constants in this file, with no external randomness. target_index cycles
round-robin across all 8 nodes (0..7) so every node serves as the fault
target roughly the same number of times across the batch.
"""

from __future__ import annotations

import json
from pathlib import Path

FAULT_TRIALS_PER_TYPE = 40
NO_FAULT_TRIALS = 16
SIEVE_LIMIT = 2_000_000
NODE_COUNT = 8

CPU_CONTENTION_INTENSITY = 2
IO_STALL_INTENSITY = 4  # bumped from the fault's own default (2): a manual
# verification run during Milestone 4 development found intensity 2 too
# weak to reliably slow the CPU-bound sieve phase; see docs/METHODOLOGY.md
# for the full discussion of this fault type's detectability.


def _fault_trials(fault_type: str, intensity: int, seed_base: int) -> list[dict[str, object]]:
    trials = []
    for i in range(FAULT_TRIALS_PER_TYPE):
        target_index = i % NODE_COUNT
        trials.append(
            {
                "trial_id": f"{fault_type}-{i:04d}",
                "fault_type": fault_type,
                "target_host": f"workload-{target_index + 1}",
                "intensity": intensity,
                "phase_index": 0,
                "sieve_limit": SIEVE_LIMIT,
                "seed": seed_base + i,
            }
        )
    return trials


def _no_fault_trials(seed_base: int) -> list[dict[str, object]]:
    return [
        {
            "trial_id": f"no-fault-{i:04d}",
            "fault_type": None,
            "target_host": None,
            "intensity": None,
            "phase_index": 0,
            "sieve_limit": SIEVE_LIMIT,
            "seed": seed_base + i,
        }
        for i in range(NO_FAULT_TRIALS)
    ]


def main() -> None:
    manifest = {
        "schema_version": 1,
        "fault_trials": (
            _fault_trials("cpu_contention", CPU_CONTENTION_INTENSITY, seed_base=10_000)
            + _fault_trials("io_stall", IO_STALL_INTENSITY, seed_base=20_000)
        ),
        "no_fault_trials": _no_fault_trials(seed_base=30_000),
    }
    out_path = Path(__file__).parent / "trial_seeds.json"
    out_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"wrote {out_path} with {len(manifest['fault_trials'])} fault trials "
          f"and {len(manifest['no_fault_trials'])} no-fault trials")


if __name__ == "__main__":
    main()
