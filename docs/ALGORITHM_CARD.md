# Algorithm Card: MAD Z-Score Straggler Ranking

## What it does

Given one completed synthetic-job phase, the algorithm ranks the participating
nodes by how anomalous their phase duration is relative to the fleet, using a
robust statistic that is not itself distorted by the anomaly it is trying to
detect. The top-ranked node above a fixed threshold is reported as the
probable straggler for that phase.

## Method

For phase durations `d_1..d_n` (nanoseconds, derived from the monotonic
clock, never the realtime clock; see `BUILD_PLAN.md` section 7):

1. Compute `median(d)` and `MAD(d) = median(|d_i - median(d)|)`.
2. Apply a 1ms floor to `MAD(d)` to avoid division by zero when every node
   finishes at nearly the same time.
3. Compute the modified z-score `M_i = 0.6745 * (d_i - median(d)) / MAD(d)`
   for each node (Iglewicz and Hoya, 1993).
4. Flag any node with `M_i > 3.5` (the commonly cited robust-outlier
   threshold from the same source).
5. Rank flagged nodes by `M_i` descending; ties broken by ascending
   `node_id` for a deterministic total order.

Implementation: `ingestion/src/hpctel/analysis/straggler.py`.

## Assumptions

- At least 3 nodes must report the phase; below that, the algorithm returns
  `insufficient_evidence` rather than a spurious ranking, since a median
  absolute deviation computed from 1 or 2 points is not a meaningful robust
  statistic.
- All participating nodes are running the same synthetic job phase (the same
  fixed-iteration-count prime sieve), so under normal conditions their
  durations should cluster tightly; a single genuinely degraded node is
  expected to be the only strong outlier.
- The threshold (3.5) and the MAD floor (1ms) are fixed constants, not
  tuned per trial or per fault type. They were set before the confirmatory
  evaluation batch and are not adjusted based on its results.

## Known failure modes (by design, not oversights)

- **Fleet-wide degradation.** If every node is equally slowed (for example,
  host-level thermal throttling affecting the whole rack), the algorithm
  cannot detect it: it ranks nodes relative to the fleet's own median, so a
  uniform slowdown looks like "no straggler," not "everyone is a straggler."
  This is an explicit non-goal, not a bug.
- **Sub-threshold contention.** A fault type or intensity that does not move
  a node's duration far enough past the fleet's median absolute deviation
  will not be flagged. The confirmatory evaluation batch measures this
  directly per fault type rather than assuming uniform sensitivity across
  fault types (see `docs/METHODOLOGY.md`); an early manual check during
  development found the `io_stall` fault type, at its original default
  intensity, produced too weak an effect on a purely CPU-bound phase
  workload to reliably trigger detection, which is why the frozen trial
  manifest (`eval/trial_seeds.json`) uses a higher `io_stall` intensity than
  `cpu_contention`, and why the confirmatory results report each fault type
  separately.
- **Single clock domain.** All simulated nodes share one physical host clock
  (BUILD_PLAN.md section 7), so this algorithm has never been evaluated
  against true cross-host clock skew. A real multi-host deployment is an
  explicit follow-on, not part of this claim.

## Root-cause tagging (secondary, non-gating)

For the single top-ranked flagged node, the algorithm compares its
during-phase CPU, I/O-wait, and network metrics against its own mean values
in the 30 seconds immediately preceding the phase, and tags the largest
relative increase above a 25% threshold as `CPU_CONTENTION`, `IO_STALL`, or
`NETWORK`; otherwise `UNKNOWN`. This is reported and evaluated (see
estimand 4 in `docs/METHODOLOGY.md`) but never gates the primary claim: a
wrong or `UNKNOWN` tag on a correctly detected straggler is a measured
limitation, not a failed detection.

## Baseline comparison

A naive maximum-duration ranking (flag whichever node simply took the
longest, with no robust statistic and no fixed threshold) is evaluated on
the exact same trial batch and reported alongside the MAD z-score method in
`docs/METHODOLOGY.md`, so the more sophisticated method's value is measured,
not assumed.

## What this algorithm does not claim

- It has not been benchmarked head-to-head against Netdata, Ganglia,
  Prometheus `node_exporter`, or the academic straggler-detection systems
  cited in `BUILD_PLAN.md` section 3 and section 20.
- It is not claimed to generalize to workloads other than the fixed-
  iteration-count synthetic phase job used in this project's evaluation.
- No production, safety, or real-time guarantee is made; see
  `docs/LIMITATIONS.md`.
