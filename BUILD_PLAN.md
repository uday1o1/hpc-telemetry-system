# HPC Telemetry System

## 1. Product Definition and Claim

HPC Telemetry System is a rack-scale telemetry collection, ingestion, and runtime diagnostics platform for Linux compute clusters.
The one-sentence product claim: given a simulated rack of Linux compute nodes running a synchronized job, the platform collects low-overhead per-node hardware and OS telemetry through a custom C++ agent, ingests it asynchronously at fleet scale, and automatically ranks the node most likely responsible for a job-wide slowdown using a statistically grounded straggler-detection algorithm, with the ranking accuracy measured against seeded fault-injection trials rather than asserted.

Primary inputs: per-node OS and hardware counters read from `/proc` and `/sys` inside each node container, plus job phase-boundary events emitted by a synthetic workload runner.
Primary outputs: a queryable time series per node and metric, a ranked straggler report per job phase with a probable root-cause tag, and correlated log and metric timelines for a chosen node and time window.

Owned technical center: the C++ node agent's OS-counter collection and batching pipeline, the custom length-prefixed protobuf wire protocol, the asyncio ingestion service and embedded time-series storage engine, and the MAD z-score straggler-ranking algorithm with its fault-injection evaluation harness.
Third-party libraries (protobuf, SQLite, FastAPI, Uvicorn) are dependencies, not the claimed contribution.

Primary falsifiable claim: on the reference 8-node simulated rack, when exactly one node is seeded with a synthetic performance fault during a job phase, the straggler-ranking algorithm identifies that node as the top-ranked candidate with a top-1 detection rate whose 95 percent Wilson lower bound is at least 0.75, while the 95 percent Wilson upper bound of the trial-level rate of falsely flagging any healthy control node is at most 0.15, both measured over the same predeclared batch of 80 seeded fault-injection trials as defined in section 13.

Secondary claims, each measured and reported rather than assumed:

- The asyncio ingestion service sustains the baseline 8-node workload with a median (across 5 warm trials) p95 end-to-end ingestion latency at or below 250 milliseconds on the reference environment defined in the compute matrix.
- The C++ node agent's steady-state resource overhead stays at or below 2 percent of one CPU core and 30 megabytes resident memory per node under the baseline workload, median across 5 warm trials.
- Seeded parsing and framing faults are rejected by the ingestion service with a recorded reason code and do not crash the service or corrupt stored data belonging to other nodes.
- On a separate batch of 16 trials with no fault injected at all, the 95 percent Wilson upper bound of the false-flag rate is at most 0.10, as an independent check that the detection threshold is not simply tuned to the fault-injection trials' own noise floor.

Tertiary, non-gating claim: the probable-root-cause tag assigned to a correctly detected straggler matches the true injected fault type at a rate reported with its own 95 percent Wilson interval; this measurement is reported honestly regardless of outcome and does not gate the primary claim above.

Claims explicitly prohibited from this project: no production-grade multi-tenant security claim, no true multi-host clock-skew correction claim, no physical hardware diagnostics claim through IPMI, Redfish, or SMART, no GPU diagnostics claim unless the optional follow-on module is built and separately evaluated, no claim that this algorithm outperforms Netdata, Ganglia, Prometheus node_exporter, or academic straggler-detection systems, since no head-to-head benchmark against them is in scope.

## 2. Primary User and Workflow

Primary user: an infrastructure, platform, or HPC systems engineer operating a fleet of Linux compute nodes who needs fast, low-overhead visibility into fleet health and a fast first answer to "which node is slowing my distributed job down" during an incident.

Main workflow demonstrated by the shipped product:

1. The user runs `docker compose up` to bring up the simulated rack, ingestion service, and dashboard.
2. The user opens the dashboard and sees live per-node CPU, memory, disk, network, and load metrics across all simulated nodes.
3. The user starts a synthetic distributed job through the CLI or dashboard, optionally seeding a fault on one target node.
4. The user watches the job run through its phases and, when it completes, opens the straggler report view.
5. The straggler report names the ranked candidate node, its z-score, and a probable root-cause tag, backed by the correlated metric and log timeline for that node and time window.
6. The user reruns the predeclared evaluation batch through the CLI to reproduce the aggregate accuracy numbers reported in the repository documentation.

This is the demonstration path used for the interview walkthrough and the portfolio-ready checkpoint.

## 3. Hiring Evidence and Public-Source Provenance

The primary evidence source for this project is the user's own target resume line, supplied directly as the seed for this build: a distributed telemetry collection and processing system built with Python, C++, FastAPI, Docker, and Linux services for rack-scale infrastructure monitoring, runtime analysis, and hardware diagnostics, with asynchronous metrics ingestion, logging, performance profiling, and CI/CD deployment workflows.
This is a single first-person target description, not a multi-role job corpus, and is treated accordingly: it defines the target skill surface rather than a statistically representative hiring sample.

Supporting public evidence, collected August 2026, used only to validate that this technical domain remains live and hiring-relevant, not to claim a representative market percentage:

- Netdata publishes HPC-specific monitoring guidance describing per-second metrics collection across compute clusters, confirming cluster-scale telemetry remains an active operational need.
- Prometheus `node_exporter` documentation describes collecting hardware and OS metrics directly from `/proc`, `/sys`, and device filesystems, which is the same data source this project's C++ agent reads, confirming the approach is grounded in a real, current operational pattern rather than an invented one.
- A 2026 arXiv preprint, "Guard: Scalable Straggler Detection and Node Health Management for Large-Scale Training," describes straggler detection as an active, current research and production problem in large training clusters, combining lightweight online monitoring with offline node sweeps, which independently corroborates that straggler identification is a real, current, technically substantive problem rather than a contrived portfolio exercise.
- A second 2026 arXiv preprint, "AntDT: A Self-Adaptive Distributed Training Framework for Leader and Straggler Nodes," further corroborates that straggler handling remains an open, actively worked problem in distributed training infrastructure.
- The user's own previously collected public job-board data (repository `job-collector`, generated 2026-08-25) includes a live posting for an NVIDIA "System Software Engineer, Distributed Systems" role, which is direct evidence that current external postings in this exact technical area exist and are publicly discoverable.

Corpus accounting: this is a purposive, single-target selection process validated with a small number of supporting public searches, not an exhaustive job-market survey.
No percentage or representativeness claim is made about the broader job market from this evidence.

## 4. Portfolio Gap and Differentiation

The user's existing local portfolio includes `job-collector`, a web-scraping and data-aggregation tool for job postings.
That project demonstrates data pipeline and scraping skill but provides no evidence of C++, Linux systems programming, concurrent network services, containerized infrastructure, performance profiling, or CI or CD pipeline ownership.
HPC Telemetry System fills that gap directly and does not duplicate `job-collector` in domain, data source, or technical center.

Differentiation from prior art, checked directly before freezing this plan:

- Prometheus `node_exporter` is a mature, widely deployed Go-based metrics exporter; this project's C++ agent covers a narrower metric set by design and is not a competing production exporter, but its wire protocol, batching, and backpressure handling are original C++ implementation work rather than a wrapper around `node_exporter`.
- Netdata and Ganglia are full observability platforms with dashboards and alerting; this project reuses none of their code and does not attempt to match their feature breadth, instead concentrating owned engineering effort on the ingestion pipeline and the straggler-ranking algorithm.
- The "Guard" and "AntDT" research systems address straggler detection in large-scale distributed training with production-scale infrastructure and proprietary telemetry; this project implements a much smaller, fully reproducible, statistically evaluated straggler-ranking method (median absolute deviation z-scoring with rule-based root-cause tagging) as an original, bounded, testable contribution, and does not claim to match or exceed their published results.
- No exact or close GitHub repository name collision was found for "HPC Telemetry System"; a near-name check on "RackTrace" and "RackPulse" surfaced only an unrelated Racket ray tracer, two small unrelated infrastructure tools, and one empty, undocumented repository, none of which overlap this project's scope.

What this project reuses: protobuf for serialization, SQLite as an embedded storage engine, FastAPI and Uvicorn for the HTTP surface, and standard Linux `/proc` and `/sys` interfaces as the data source.
What this project owns: the wire protocol and framing, the C++ collection and batching pipeline, the time-series schema and downsampling logic, the straggler-ranking algorithm, the fault-injection and statistical evaluation harness, and the correlated debugging timeline view.

## 5. Scope: V1 Boundary, Portfolio-Ready Checkpoint, Follow-Ons, and Non-Goals

Milestone 0 feasibility work: toolchain and protocol spike proving the tiny end-to-end vertical slice described in Milestone 0 below.

Portfolio-ready core (must be independently demonstrable and measurable, corresponds to Milestone 4): the full 8-node simulated rack, the C++ agent, the asyncio ingestion pipeline, the synthetic job and fault injector, the straggler-ranking algorithm, and the predeclared statistical evaluation batch with a truthful pass, fail, or insufficient-evidence result.

Extended V1 (Milestones 5 through 8): formal performance benchmarking, the debugging timeline view and CLI polish, CI and CD with container scanning and image publishing, and final documentation, licensing, and the tagged release.

Follow-on releases, explicitly out of V1 and never a mandatory gate for any V1 milestone:

- An optional GPU telemetry collector module using `nvidia-smi` or DCGM bindings, runnable only where an NVIDIA GPU is actually present, such as a Colab Pro session.
- True multi-host deployment across physically or virtually separate machines with NTP-aware clock-skew correction.
- Authentication, authorization, and multi-tenant isolation.
- A Kubernetes DaemonSet packaging of the agent.
- Slurm-integrated telemetry collection on a real university HPC cluster, for a larger simulated or real rack.
- Migration of the wire protocol to gRPC.
- Replacing the SQLite-backed storage engine with a horizontally scaled time-series database.

Non-goals for this project at any milestone: physical rack or IPMI or Redfish sensor integration, production safety or SLA claims, wide-area network deployment, multi-tenant authentication, and any claim that the straggler algorithm has been benchmarked head-to-head against Netdata, Ganglia, node_exporter, or the research systems cited in the hiring evidence section.

## 6. System Architecture and Component Ownership

Components, responsibilities, inputs, outputs, failure modes, and language:

| Component | Responsibility | Inputs | Outputs | Failure mode | Language |
| --- | --- | --- | --- | --- | --- |
| Node agent (`agent/`) | Sample `/proc` and `/sys` counters, batch, frame, and send over TCP | Kernel counters via `/proc`, `/sys` | Length-prefixed protobuf frames over TCP | On send failure, buffer up to a bounded queue, then drop oldest and log a `queue_overflow` event; never blocks the sampling loop | C++17 |
| Workload runner (`workload/`) | Run a synthetic CPU-bound phase job per node and optionally inject a seeded fault | Job start command, fault manifest | Phase-boundary events over TCP | On crash, the container's health check reports unhealthy and the phase is marked `error` in the phase-event schema | Python 3.12 |
| Ingestion server (`ingestion/src/hpctel/ingest_server.py`) | Accept concurrent agent TCP connections, decode and validate frames, write to storage | Protobuf frames | Validated rows in the time-series store | On a malformed frame, reject with a recorded reason code and keep the connection and other nodes' data intact | Python 3.12, asyncio |
| Storage engine (`ingestion/src/hpctel/storage/tsdb.py`) | Own the metric and phase-event schema, retention, and downsampling | Validated samples and phase events | Query results for the API and analysis layer | On disk-write failure, fail the write loudly to the caller rather than silently dropping data | Python 3.12, SQLite |
| Analysis engine (`ingestion/src/hpctel/analysis/straggler.py`) | Compute the straggler ranking and root-cause tag per completed job phase | Phase durations and resource metrics from storage | Ranked straggler report | On insufficient reporting nodes for a phase, return `INSUFFICIENT_EVIDENCE` rather than a spurious ranking | Python 3.12 |
| REST and dashboard API (`ingestion/src/hpctel/api.py`) | Serve query endpoints and the server-rendered dashboard | HTTP requests | JSON responses and HTML pages | On an internal error, return a structured error body and log with a correlation id | Python 3.12, FastAPI |
| CLI (`cli/src/racktl`) | Give the user a scriptable entry point for common operations | Command-line arguments | REST calls and formatted terminal output | On a network error, print a clear, actionable message and a non-zero exit code | Python 3.12 |
| Evaluation harness (`eval/run_trials.py`) | Orchestrate the predeclared seeded fault-trial batch and compute the statistical decision | Trial seed manifest | Trial-batch results and the PASS, FAIL, or INSUFFICIENT_EVIDENCE report | On a trial infrastructure error, mark that trial `ABORTED` and exclude it from the confirmatory count rather than counting it as a detection failure | Python 3.12 |

Ownership boundaries: all kernel-counter reading and wire-protocol framing on the sending side is C++.
All ingestion, storage, analysis, evaluation, and the HTTP and dashboard surface are Python.
Docker and GitHub Actions own build, packaging, and CI or CD orchestration and contain no product logic.
The architecture is intentionally single-host and local-first: all "nodes" are Docker containers on one Docker Desktop Linux VM, not physically separate machines, which is stated plainly in the non-goals and in the data contract's clock-domain section below.

## 7. Data, Schema, Time, and Identity Contracts

Schema version: `schema_version` is a `uint32` carried on every `SampleBatch`, starting at `1`.
A breaking schema change increments this value and both the C++ agent and the Python decoder must reject a batch whose `schema_version` they do not recognize, with a recorded `schema_mismatch` reason code, rather than attempting a best-effort parse.

Producer version: every `SampleBatch` carries `producer_version`, a string set at agent build time from the short Git commit SHA, so a stored sample can be traced back to the exact agent build that produced it.

Identity: `node_id` is a string configured through the `NODE_ID` environment variable at container start and is stable across agent restarts as long as the container is not recreated with a different id.
`job_id` is a UUID4 generated by the workload runner's job orchestrator at job start and is stable for the lifetime of that job across all participating nodes.

Units and coordinate conventions: `cpu_pct` and `iowait_pct` are percentages in the range 0 to 100 as doubles.
`mem_used_bytes`, `mem_total_bytes`, `disk_read_bytes_s`, `disk_write_bytes_s`, `net_rx_bytes_s`, and `net_tx_bytes_s` are all in bytes or bytes per second, never kilobytes, megabytes, or bits, and no field name may be reused for a different unit.
`load1` is the standard Linux one-minute load average as reported by `/proc/loadavg`.
`proc_count` is an integer count of processes visible in `/proc` at sample time, transmitted as a double for schema simplicity.

Canonical metric id mapping, defined once in `proto/telemetry.proto` comments and mirrored in both the C++ header and the Python constants module, and never redefined elsewhere:

| metric_id | Name | Unit |
| --- | --- | --- |
| 1 | cpu_pct | percent |
| 2 | mem_used_bytes | bytes |
| 3 | mem_total_bytes | bytes |
| 4 | load1 | load average |
| 5 | iowait_pct | percent |
| 6 | disk_read_bytes_s | bytes per second |
| 7 | disk_write_bytes_s | bytes per second |
| 8 | net_rx_bytes_s | bytes per second |
| 9 | net_tx_bytes_s | bytes per second |
| 10 | proc_count | count |

Timestamp units, epochs, and clock domains: `ts_ns` is nanoseconds since the Unix epoch, read from `CLOCK_REALTIME` on the agent at sample time.
`server_recv_ts_ns` is nanoseconds since the Unix epoch, set by the ingestion server at frame receipt and left at zero on the wire from the agent.
Every simulated node in V1 is a container on the same Docker Desktop Linux virtual machine and therefore shares one physical clock, so no cross-host clock-skew correction is implemented or claimed; this is an explicit, stated limitation, not an oversight, and is repeated in the limitations documentation.

Monotonic duration and rate fields: `CLOCK_REALTIME` is wall-clock time and can step backward or forward under NTP correction, so it is never used for elapsed-time math.
Every `Sample` and `PhaseEvent` additionally carries a `mono_ns` (`Sample`) or `phase_start_mono_ns` and `phase_end_mono_ns` (`PhaseEvent`) field, read from `CLOCK_MONOTONIC` on the agent at the same instant as the corresponding `ts_ns` field.
All elapsed-time computations, including every rate derivation in the transform-direction paragraph below and the phase-duration input to the straggler algorithm in section 8, use only the monotonic fields; `ts_ns` and `server_recv_ts_ns` are used exclusively for wall-clock display, correlation with logs, and ordering, never for a duration or a rate.

Null, unknown, invalid, and missing states: a metric that cannot be read for one sample cycle, such as a transient `/proc` read failure, is simply omitted from that cycle's batch rather than sent as a sentinel value, and the storage layer treats a gap in a series as "no data," never as zero.

Transform direction: the agent always reads raw kernel counters and derives rates, such as `disk_read_bytes_s`, from consecutive raw counter deltas divided by the elapsed wall time between samples; the storage layer never re-derives a rate from another rate, only from stored raw or previously derived values with a documented derivation function.

Ordering and serialization: samples within one `SampleBatch` are ordered by `ts_ns` ascending as produced by the agent; the storage layer's primary key is `(node_id, metric_id, ts_ns)` and a duplicate primary key on insert is an idempotent no-op, not an error, so a retried batch cannot corrupt the store.

Raw-source preservation: the storage engine never overwrites a raw sample row; downsampled rollups are written to separate rollup tables (`rollup_1m`, `rollup_1h`) computed from raw rows, so raw data always remains the source of truth and a rollup can be recomputed and verified against it.

Artifact hashes and lineage: every evaluation trial-batch result file and every performance benchmark result file is written with a SHA-256 content hash recorded in its accompanying manifest, and the manifest records the exact Git commit the run was produced from.

## 8. Algorithms: Straggler Ranking and Root-Cause Tagging

Mathematical inputs: for one completed job phase identified by `(job_id, phase_index)`, the set of `phase_duration_ns` values, one per reporting node, computed as `phase_end_mono_ns - phase_start_mono_ns` using the monotonic fields defined in section 7, never the realtime `ts_ns` fields.

Objective: identify the node whose phase duration is most anomalous relative to the fleet, using a method that is robust to the influence of the anomalous value itself on the reference statistic.

Method: the modified z-score of Iglewicz and Hoya, `M_i = 0.6745 * (d_i - median(d)) / MAD(d)`, where `d` is the vector of phase durations, `median(d)` is the sample median, and `MAD(d)` is the median absolute deviation from the median.
A floor of one millisecond in nanoseconds is applied to `MAD(d)` before division to avoid division by zero when all nodes finish at nearly identical times.
A node is flagged as a straggler candidate when `M_i` exceeds a predeclared threshold of 3.5, the commonly cited robust-outlier threshold from Iglewicz and Hoya's 1993 paper.
Flagged nodes are ranked by `M_i` descending; the top-ranked node is the reported straggler candidate for that phase.

State representation: the algorithm's state for one phase is exactly the vector of `(node_id, phase_duration_ns)` pairs for that phase; it holds no cross-phase or cross-job state, so a phase's ranking is fully reproducible from that phase's own event rows alone.

Constraints and deterministic tie-breaking: ties in `M_i` are broken by ascending lexicographic `node_id`, so the ranking is a total order and reproducible given identical input rows.

Complexity and memory bounds: O(N log N) per phase for the median and MAD computation, where N is the number of reporting nodes for that phase; V1 bounds N to 64, so this is not a performance concern.

Failure and inconclusive states: if fewer than 3 nodes report a phase-end event, the algorithm returns `INSUFFICIENT_EVIDENCE` for that phase rather than a ranking, since a median absolute deviation computed from 1 or 2 points is not a meaningful robust statistic.

Reference baseline for comparison, not as the shipped detector: a naive maximum-duration ranking that simply flags the single node with the largest `phase_duration_ns`, with no robust statistic and no fixed threshold.
The evaluation harness computes and reports the detection and false-positive rates of both the MAD z-score method and this naive baseline side by side, so the plan does not assume the more sophisticated method wins without measuring it.

Root-cause tagging, applied only to the top-ranked flagged node: compare that node's mean `cpu_pct`, `iowait_pct`, `net_rx_bytes_s`, and `net_tx_bytes_s` during the flagged phase window against that same node's own mean values over the 30 seconds immediately preceding the phase.
Tag `CPU_CONTENTION` if the largest relative increase is in `cpu_pct`, `IO_STALL` if it is in `iowait_pct`, `NETWORK` if it is in the combined receive and transmit rate, and `UNKNOWN` if no metric shows a relative increase greater than 25 percent over its own pre-phase baseline.

Unit, golden, property, and metamorphic tests for this algorithm, implemented in Milestone 4: a golden test with a hand-computed 5-node example verifying the exact `M_i` values and ranking; a property test asserting that adding a duplicate copy of the median-duration node never changes which node is top-ranked; a metamorphic test asserting that multiplying every node's `phase_duration_ns` by the same positive constant never changes the ranking, since `M_i` is scale-invariant under a shared positive multiplier once the MAD floor is not binding; and a boundary test confirming the `INSUFFICIENT_EVIDENCE` path fires at exactly 2 reporting nodes and does not fire at exactly 3.

## 9. Repository Layout

Concrete file tree for the repository root:

```text
hpc-telemetry-system/
  BUILD_PLAN.md
  README.md
  LICENSE
  .gitignore
  docker-compose.yml
  docker-compose.ci.yml
  proto/
    telemetry.proto
  agent/
    CMakeLists.txt
    src/
      main.cpp
      proc_reader.hpp
      proc_reader.cpp
      framing.hpp
      framing.cpp
      sender.hpp
      sender.cpp
      config.hpp
      config.cpp
      logging.hpp
      logging.cpp
    tests/
      fixtures/
      test_proc_reader.cpp
      test_framing.cpp
    Dockerfile
  ingestion/
    pyproject.toml
    src/hpctel/
      api.py
      ingest_server.py
      models.py
      config.py
      logging_utils.py
      storage/
        schema.py
        tsdb.py
      analysis/
        straggler.py
        stats.py
    tests/
      unit/
      integration/
    Dockerfile
  workload/
    src/workloadrunner/
      runner.py
      faults.py
    Dockerfile
  dashboard/
    templates/
    static/
      vendor/
  cli/
    src/racktl/
      __main__.py
  eval/
    trial_seeds.json
    run_trials.py
    results/
  scripts/
    dev_up.sh
    run_ci_integration_test.sh
  .github/
    workflows/
      ci.yml
  docs/
    ARCHITECTURE.md
    METHODOLOGY.md
    PERFORMANCE.md
    LIMITATIONS.md
    ALGORITHM_CARD.md
```

Committed: all source under `agent/`, `ingestion/`, `workload/`, `dashboard/`, `cli/`, `eval/` (excluding `eval/results/`), `proto/`, `scripts/`, `.github/`, `docs/`, and the root configuration and documentation files.
Ignored through `.gitignore`: build directories (`agent/build/`), Python virtual environments and caches, `eval/results/*` raw trial output beyond the committed summary report, SQLite database files created at runtime, and any local `.env` file.
Generated at build or CI time and never committed: Docker images, the CMake build tree, Python wheels, and the `eval/results/` raw trial artifacts, which are instead published as a content-addressed evidence bundle referenced by hash from `docs/METHODOLOGY.md`.
Restricted or downloaded: none; this project uses no external dataset and requires no license acceptance, since all telemetry is generated locally by the synthetic workload and fault injector.

## 10. Toolchain, Dependency, and Environment Strategy

C++ toolchain: C++17, built with CMake and Ninja or Make inside the Linux container image, using `libprotobuf-dev` installed from the Debian or Ubuntu base image's package manager for the agent build stage, and GoogleTest for the C++ unit tests, pinned to a version resolved and recorded at implementation time from the official GoogleTest GitHub releases page.

Python toolchain: Python 3.12, dependency locking through `uv` or `pip-tools` with a committed lock file, `pytest` for tests, `ruff` for linting and formatting, and `mypy` for static typing on the `ingestion` and `eval` packages.
FastAPI and Uvicorn versions are not hardcoded in this plan; the implementation agent must resolve the current stable release from the official FastAPI documentation at `https://fastapi.tiangolo.com` and PyPI at implementation time and record the exact resolved version and hash in the committed lock file, since a version number quoted from an unverified web search result is not a trustworthy pin.

Protobuf schema compiler: `protoc`, with the C++ and Python bindings generated from the single `proto/telemetry.proto` source of truth at build time inside each component's Dockerfile, never hand-written or committed as generated code, so the two language bindings cannot drift out of sync.

Containers: every component ships its own Dockerfile using a pinned, digest-referenced base image, builds and runs as a non-root user, and exposes only the ports it needs; `docker-compose.yml` wires the rack together on an internal Docker network with only the dashboard's port published to the host loopback interface.

Version strategy: every pinned dependency, container base image, and toolchain version is recorded in a single `docs/ARCHITECTURE.md` "pinned versions" table, updated whenever a pin changes, so the exact environment used for any reported result is always reconstructible.

## 11. Synthetic Workload and Fault-Injection Provenance

No external dataset is used or required by this project; all telemetry data is generated locally by the synthetic workload runner and the real Linux kernel counters of the containers it runs in, so there is no dataset license, redistribution, or missing-modality concern to resolve.

Synthetic job: the workload runner exposes a `start_job` command that, for a configured number of phases, runs a bounded CPU-bound computation, such as a fixed-iteration-count prime sieve, on every participating node simultaneously, and reports a `PhaseEvent` with `phase_start_ts_ns`, `phase_start_mono_ns`, `phase_end_ts_ns`, and `phase_end_mono_ns` back to the ingestion server over the same TCP wire protocol used by the agent, using the same realtime and monotonic field pairing defined in section 7.

Fault injection: the fault manifest names a `target_node_id`, a `phase_index`, a `fault_type` (`cpu_contention`, meaning extra busy-spin threads started inside that node's workload-runner process for the duration of the phase, or `io_stall`, meaning repeated bounded synchronous file writes and `fsync` calls inside that node's container for the duration of the phase), an intensity parameter, and a random seed.
All fault injection happens inside the target container's own userspace process; V1 deliberately avoids `tc netem` and any `NET_ADMIN` or privileged container capability, so the fault injector never requires elevated container privileges, which keeps the security contract in section 12 simple and portable across Docker Desktop configurations.

Immutable trial identity: every fault-injection trial is assigned a `trial_id` combining `job_id` and the fault manifest's seed, and every trial's full input manifest, including the fault type, target node, phase index, and intensity parameter, and its output result, is written to `eval/results/<trial_id>.json`, so a trial can never silently overwrite another trial's evidence.
The intensity parameter is frozen in `eval/trial_seeds.json` alongside the seed before Milestone 4's confirmatory batch begins, exactly like the seed itself, so intensity cannot be hand-tuned after seeing early results.

Within-trial negative controls: in every fault-injection trial, the seven non-target nodes run the same synthetic job phase with no injected fault.

No-fault control trials: in addition to the 80 fault-injection trials, `eval/trial_seeds.json` predeclares a separate batch of 16 no-fault trials, each running the same synthetic job across all 8 nodes with no fault injected on any node, used to establish the baseline, noise-driven false-flag rate with no confound from a genuinely faulted sibling node sharing the same host.
This batch is defined and frozen before Milestone 4 begins, with its own fixed seeds, and is never used to tune the algorithm's threshold after being run.

## 12. Testing, Fault Oracle, and Security Contract

Test strategy by layer: C++ unit tests (GoogleTest) for `proc_reader` parsing against committed fixture files that mimic real `/proc` contents, so tests never depend on the actual host's live `/proc` state; C++ unit tests for the framing and length-prefix logic, including round-trip and corrupted-input cases; Python unit tests for the storage schema, the downsampling rollup logic, and the straggler-ranking algorithm, including the golden, property, and metamorphic tests defined in section 8; Python integration tests that start the ingestion server and a scripted fake agent client over a real TCP socket and assert end-to-end delivery; and one docker-compose-based end-to-end test that brings up a small 3-node rack, runs one job with one seeded fault, and asserts the correct node is flagged.

Closest real user-path verification, run at Milestone 4 and again at final release: a clean `docker compose up` followed by the documented CLI commands to start a job, inject a fault, and read the straggler report, exactly as a real user would run it, not just an isolated unit test of the ranking function.

Fault and oracle contract, covering deterministic, seeded faults with a frozen expected outcome and a nearby negative control so the ingestion service cannot pass its fault tests by rejecting everything:

| Fault class | Seeded fault | Expected outcome | Negative control |
| --- | --- | --- | --- |
| Transport | Connection dropped mid-batch | Partial batch discarded, `partial_frame` reason code logged, connection can reconnect and resume | A complete batch on a healthy connection is accepted normally |
| Parsing | Truncated length prefix | Frame rejected with `truncated_frame` reason code, connection not torn down | A correctly framed batch immediately after is accepted |
| Schema | `metric_id` outside the canonical mapping table | Sample dropped with `unknown_metric_id` reason code, rest of the batch still processed | A batch with only known `metric_id` values is fully accepted |
| Schema | `schema_version` the server does not recognize | Entire batch rejected with `schema_mismatch` reason code | A batch at the current `schema_version` is accepted |
| Temporal | `ts_ns` more than 24 hours in the future or before the Unix epoch | Sample dropped with `invalid_timestamp` reason code | A sample with a timestamp within the last minute is accepted |
| Ground-truth-invalid | Fewer than 3 nodes report a phase | Analysis returns `INSUFFICIENT_EVIDENCE`, not a ranking | A phase with 3 or more reporting nodes returns a ranking |

Security and privacy contract: trust boundary is the Docker internal network; only the dashboard's HTTP port is published to the host, bound to `127.0.0.1`, and V1 ships with no authentication, which is an explicit, documented non-goal rather than an oversight, since the intended demonstration environment is a single-user local machine.
All input validation for the wire protocol happens at frame-decode time in the ingestion server, exactly as enumerated in the fault and oracle table above.
No path or archive handling exists in this project, since no file uploads or archive extraction occur anywhere in the system, so path and archive traversal are not applicable attack surfaces.
No secrets or credentials are used by any V1 component.
Every container Dockerfile creates and runs as a dedicated non-root user.
CI runs a container image vulnerability scan with `trivy` (or the current equivalent named in Milestone 7) against every built image and fails the build on a high or critical finding with no known false-positive suppression added without a documented justification.
Logs and stored artifacts never contain secrets, since none exist in this system, and the evaluation result bundle contains only `node_id` values, metric values, and timestamps, none of which are personal or sensitive data.

## 13. Evaluation Metrics and Statistical Decision Contract

This project trains no machine learning model, so the ML experiment contract is not applicable; the confirmatory evaluation instead uses the statistical decision contract below over the seeded fault-injection trial batch defined in section 11.

Estimand 1, top-1 detection rate: the probability that the MAD z-score algorithm's top-ranked node in a trial is exactly the seeded fault's `target_node_id`, evaluated over the 80-trial fault-injection batch from section 11.

Estimand 2, trial-level false-positive rate: the probability that at least one of the seven healthy negative-control nodes in a trial is flagged (exceeds the `M_i` threshold of 3.5).
This estimand is defined at the trial level, one binary indicator per trial, not per individual node, because all 8 simulated nodes share one physical host and Docker Linux VM, so a fault on the target node can plausibly perturb sibling containers' readings within the same trial; treating each of the 7 controls as an independent Bernoulli draw would overstate the effective sample size and produce an artificially narrow interval.
Estimand 2 is evaluated over the same 80-trial fault-injection batch as estimand 1, giving it the same independent unit and the same trial count.

Estimand 3, no-fault baseline false-flag rate: the probability that any node is flagged in a trial where no fault was injected at all, evaluated over the separate 16-trial no-fault control batch from section 11, reported alongside estimand 2 as an independent check that the threshold is not simply miscalibrated to the fault-injection trials' own noise floor.

Estimand 4, root-cause tag accuracy: the probability that the root-cause tag assigned to the correctly identified top-ranked node matches that trial's true injected `fault_type` (`CPU_CONTENTION` for `cpu_contention`, `IO_STALL` for `io_stall`), evaluated only over the subset of the 80-trial batch where estimand 1's detection succeeded, since tag accuracy is conditional on detection having already happened.

Independent resampling unit: one fault-injection trial, meaning one full docker-compose rack run with one seeded fault, for estimands 1, 2, and 4; one no-fault trial for estimand 3.

Minimum independent trial count, predeclared before any trial is run and frozen in `eval/trial_seeds.json` before Milestone 4 begins: 40 `cpu_contention` trials and 40 `io_stall` trials, 80 total, for estimands 1, 2, and 4; a separate 16 no-fault trials for estimand 3.

Point estimate and confidence interval method: the sample proportion for each estimand, with a 95 percent Wilson score interval, chosen because it stays well-behaved near proportions of 0 or 1 where a normal approximation interval breaks down, and because it needs no resampling procedure beyond the observed trial count.

Lower-bound rule for the benefit claim: estimand 1's top-1 detection rate passes only if the 95 percent Wilson lower bound is at least 0.75.

Upper-bound rules for the harm claims: estimand 2's trial-level false-positive rate passes only if the 95 percent Wilson upper bound is at most 0.15; estimand 3's no-fault false-flag rate passes only if the 95 percent Wilson upper bound is at most 0.10, a stricter bound since no fault is present at all in that batch.

Tertiary threshold, non-gating: estimand 4's tag accuracy is reported with its Wilson interval but does not gate the `PASS` decision below, since it is a secondary product feature (root-cause hinting) layered on top of the primary detection claim, not the primary claim itself; a lower bound below 0.5 is called out explicitly as a known limitation in `docs/ALGORITHM_CARD.md` rather than hidden.

Zero-event upper-bound rule: if zero events are observed for any estimand across its trial batch, the reported upper bound is the Wilson upper bound computed at zero successes over that batch's trial count, never asserted as literally zero percent.

Trial-exclusion rule: a trial is excluded from every estimand's denominator, and logged as `ABORTED`, only for a genuine infrastructure failure, meaning a container crash, an unrecoverable Docker or network error, or a process that never completed startup, none of which reflect the algorithm's own behavior.
A phase-level `INSUFFICIENT_EVIDENCE` result from the algorithm itself (fewer than 3 nodes reporting) during a confirmatory trial is never excluded; it counts as a non-detection for estimand 1 and, where applicable, a non-flag for estimands 2 and 3, exactly like any other observed outcome, so that an ambiguous internal result can never be quietly dropped from the confirmatory count.

Multiple-comparison handling: the naive maximum-duration baseline from section 8 is evaluated on the exact same 80-trial fault-injection batch and reported alongside the MAD z-score method's estimands 1 and 2, using paired evaluation on identical trials for both methods, so the comparison is fair and not subject to separate, cherry-picked trial sets.

Freeze and final-holdout contract: the exact Git commit implementing `analysis/straggler.py`, `analysis/stats.py`, and every threshold named above is tagged `eval-frozen-v1` at the moment the Milestone 4 confirmatory batch first executes to completion.
The Milestone 4 result computed against that frozen commit and the frozen `eval/trial_seeds.json` manifest is the one and only confirmatory claim; it is not re-earned or re-derived later.
The `v1.0.0` final release in section 19 replays the same frozen trial manifest against the exact `eval-frozen-v1` commit purely as a determinism check (the numbers must match exactly, since nothing that affects the algorithm changed), not as a second, independent confirmatory run.
If a defect in the algorithm is discovered after `eval-frozen-v1` and must be fixed, the fix is made, a new, previously unused seed manifest is generated for both the fault-injection and no-fault batches, a new confirmatory batch is run against the fixed code, and the new commit is tagged `eval-frozen-v2`; the `eval-frozen-v1` result and manifest are kept in the repository history and never silently overwritten, and `docs/METHODOLOGY.md` reports both the original and the corrected result with the reason for the correction.

Decision states, evaluated independently for estimands 1, 2, and 3: `PASS` when the estimand's bound rule above is met using its full predeclared trial count; `FAIL` when the full predeclared trial count completed but the bound rule is not met, reported honestly in `docs/METHODOLOGY.md` with an analysis of which fault type or root cause drove the shortfall, and not treated as blocking the portfolio-ready checkpoint, since a truthful negative result with root-cause analysis is itself valid evaluation-strength evidence; `INSUFFICIENT_EVIDENCE` when fewer than the predeclared minimum trial count completed without every excluded trial meeting the strict `ABORTED` definition above, which must never be reported as `PASS` or `FAIL`.
The primary claim in section 1 is considered supported only when estimands 1 and 2 both reach `PASS`.

Performance benchmark protocol (Milestone 5), separate from the confirmatory statistical gate above: named environment is the Apple M2 MacBook Pro with 8 gigabytes of unified host memory and the 4 gigabyte Linux VM allocation from section 15, with the exact Docker or Colima version and container kernel version (`uname -r` inside the container) recorded at run time; workload manifest is the 8-node baseline at a 1-second sample interval and a stress configuration at a 200-millisecond sample interval; a 30-second warm-up window is discarded before any latency is measured; 5 independent 5-minute trials per configuration are run in randomized order; reported statistics are the median and interquartile range across those 5 trials for p50, p95, and p99 end-to-end ingestion latency, throughput, and agent CPU and resident-memory overhead; a trial is discarded and rerun if host CPU thermal throttling is detected through a greater than 20 percent drop in reported clock frequency between the trial's start and end, checked from the macOS host, not from inside the Linux VM.

## 14. User Experience: CLI, API, and Dashboard

REST API surface, served by FastAPI on the dashboard container:

- `GET /api/nodes` lists known nodes and their last-seen timestamp.
- `GET /api/metrics/{node_id}/{metric_name}` returns a time series for one node and metric over a requested time range, downsampled automatically when the range exceeds a threshold.
- `POST /api/jobs` starts a synthetic job, optionally with a fault manifest, and returns a `job_id`.
- `GET /api/jobs/{job_id}` returns job status and, once complete, the per-phase straggler report.
- `GET /api/jobs/{job_id}/timeline/{node_id}` returns the correlated metric and log timeline for one node across the job's time window, backing the debugging use case named in the product claim.
- `GET /healthz` returns liveness and readiness for the ingestion and storage layers.

CLI (`racktl`), a thin wrapper over the REST API so the entire product can be driven without a browser: `racktl nodes`, `racktl start-job [--fault node=<id>,type=<type>,phase=<n>]`, `racktl job-status <job_id>`, `racktl timeline <job_id> <node_id>`, and `racktl run-eval-batch` which reproduces the predeclared trial batch from `eval/trial_seeds.json`.

Dashboard: a server-rendered FastAPI and Jinja2 page with a small amount of vanilla JavaScript polling the REST API, using one pinned, vendored copy of a lightweight charting library committed under `dashboard/static/vendor/` rather than loaded from a content delivery network, so the demonstration works fully offline and is fully reproducible without a live third-party dependency.
The dashboard shows a fleet health grid, an active job view with live phase progress, the straggler report view with the ranked node and root-cause tag, and the correlated timeline view for a selected node.

## 15. Compute Matrix and Resource Ladder

The host is an Apple M2 MacBook Pro with 8 gigabytes of unified memory, running a Linux virtual machine (Colima or Docker Desktop) allocated a fixed 4 gigabytes of memory and 2 CPUs, leaving the remaining host memory for macOS, the terminal, and development tooling.
The "memory budget" referenced throughout this plan means the Linux VM's allocated 4 gigabytes, not the host's full 8 gigabytes, and actual VM memory use (`docker stats` aggregate, or the VM's own reported usage) is measured starting at Milestone 1, not deferred to Milestone 3.

| Workload | Preferred resource | Minimum resource | Expected duration | Checkpoint strategy | Required evidence | Fallback |
| --- | --- | --- | --- | --- | --- | --- |
| Local development, unit and integration tests, 8-node rack simulation | Local Apple M2 MacBook Pro, 4 gigabyte Linux VM allocation, Docker Desktop or Colima | Same | Seconds to minutes per run | Not applicable, stateless test runs | Test run output and CI logs | Reduce the rack to 6 nodes (5 healthy negative-control nodes) if memory pressure is observed; never below 6, since the algorithm's own `INSUFFICIENT_EVIDENCE` floor in section 8 requires at least 3 reporting nodes and a smaller rack leaves too little margin above that floor |
| Confirmatory evaluation batch: 80 fault-injection trials plus 16 no-fault control trials | Local Apple M2 MacBook Pro, 4 gigabyte Linux VM allocation, Docker Desktop or Colima | Same | Roughly 1 to 2 hours for the full batch | Each trial result written to `eval/results/<trial_id>.json` immediately, so the batch can resume by skipping already-completed seeds | Trial-batch results directory and the Wilson confidence interval report in `docs/METHODOLOGY.md` | No reduction below the predeclared 80 fault-injection and 16 no-fault trial counts is permitted for a `PASS` claim; a smaller completed count must be reported as `INSUFFICIENT_EVIDENCE` |
| CI build, test, and image scan | GitHub Actions Linux runner, free tier | Same | Under 15 minutes per run | Stateless per workflow run | CI workflow logs and the container scan report artifact | Skip the image publish step if GHCR access is unavailable, keep build, test, and scan |
| Performance benchmark protocol | Local Apple M2 MacBook Pro, 8 gigabyte host, 4 gigabyte Linux VM allocation, Docker Desktop or Colima | Same | Roughly 1 hour for all configurations and trials | Each trial's raw measurements appended to a run-log file | `docs/PERFORMANCE.md` results table and the content-addressed raw measurement bundle | Reduce to 3 trials per configuration and label the interval as wider and less certain |
| Optional GPU telemetry follow-on (not V1) | Google Colab Pro accelerator runtime | Colab Pro T4 | Under 30 minutes, exploratory spike | Manual, not resumable, exploratory only | Accelerator capability probe output and a sample metric batch | Ship without the GPU module and mark it unavailable in the README |
| Optional larger-scale rack or Slurm integration (not V1) | A university HPC cluster, Slurm CPU partition | Same | Under 1 hour, bounded batch job | Slurm job checkpointed under a no-clobber run identifier | Job log and result manifest retrieved to the local machine for verification | Stay at the 8 to 12 node local scale and label the larger-scale claim a follow-on |

No milestone in the portfolio-ready core or the extended V1 depends on Colab, a university HPC cluster, or any paid cloud resource; all three are reserved for explicitly optional, clearly labeled follow-on work.

## 16. Milestones, Acceptance Gates, and Commit Boundaries

**Milestone 0, feasibility spike.**
Objective: prove the toolchain, the protocol, and a tiny end-to-end vertical slice work before committing to the full build.
Deliverables: a minimal C++ program that reads one real `/proc/stat` value and builds inside the Linux container image; `proto/telemetry.proto` compiling successfully into both C++ and Python bindings from one schema; a minimal `docker compose up` bringing up one agent container and one ingestion container within the 4 gigabyte Linux VM memory budget defined in section 15; one real metric sample flowing from the agent through the wire protocol into SQLite and back out through one FastAPI `GET` endpoint.
Required tests: a smoke test asserting the end-to-end slice produces a retrievable sample.
Acceptance gate: `docker compose up` followed by one documented `curl` command returns the one real sample with correct `node_id`, `metric_id`, and a plausible `ts_ns`.
Kill or fallback decision: if `libprotobuf` cannot be reliably installed and linked inside the Linux build image within a reasonable time, fall back to a hand-rolled binary framing format with fixed-width fields instead of protobuf, documented as a deliberate substitution in `docs/ARCHITECTURE.md`.
Commit boundary: one focused commit, "feat: milestone 0 end-to-end telemetry slice."
Hardware or external dependency state: none, fully local.

**Milestone 1, C++ node agent.**
Objective: build the complete, tested node agent.
Deliverables: full `/proc` and `/sys` parsing for all 10 canonical metrics, batching, the length-prefixed framing implementation, a background sender thread with a bounded queue and documented drop-oldest backpressure policy, structured JSON logging, and environment-variable configuration.
Required tests: GoogleTest unit tests for every parser against committed fixture files, and framing round-trip and corruption tests.
Closest real user-path verification: the agent binary run standalone against a mock TCP listener delivers a correct batch matching the fixture-derived expected values.
Acceptance gate: `ctest` passes fully in the CI-equivalent local build, and the agent successfully connects to and streams into a scripted mock listener for 60 continuous seconds with zero unexpected disconnects; the running agent container's resident memory is measured (`docker stats`) and recorded as the first data point toward the 4 gigabyte Linux VM memory budget from section 15, rather than deferring any memory measurement to Milestone 3.
A minimal GitHub Actions workflow building and running `ctest` for the agent is added at this milestone as a baseline check; Milestone 7 later extends this same workflow with the Python build, integration tests, container scanning, and image publishing rather than introducing CI for the first time.
Commit boundary: one focused commit per logical sub-component (parser, framing, sender), each preceded by its own passing tests.
Hardware or external dependency state: none, fully local.

**Milestone 2, asyncio ingestion and storage.**
Objective: build the ingestion service and the owned time-series storage engine.
Deliverables: the asyncio TCP listener, the FastAPI REST surface for node and metric queries, the SQLite-backed storage schema with write-ahead logging, and the 1-minute and 1-hour downsampling rollup jobs.
Required tests: unit tests for the storage schema, insert, query, and rollup correctness; integration tests using a scripted fake agent client sending real frames over a real TCP socket; the full fault and oracle table from section 12 implemented as tests with the expected reason codes asserted.
Closest real user-path verification: `docker compose up` for the ingestion service plus a documented test-client script reproduces N samples end-to-end, retrievable through the REST API within a documented latency bound.
Acceptance gate: all fault-oracle tests pass with the correct reason codes, all negative controls pass, and the end-to-end test-client run succeeds.
Commit boundary: one focused commit per sub-component (TCP listener, storage schema, rollup logic, REST endpoints), each with passing tests.
Hardware or external dependency state: none, fully local.

**Milestone 3, rack simulation and synthetic workload.**
Objective: bring up the full 8-node simulated rack and the synthetic job.
Deliverables: the complete `docker-compose.yml` for 8 node containers plus ingestion and dashboard, the workload runner's `start_job` orchestration, and the phase-event schema wired end to end.
Required tests: an integration test that starts a job across all 8 nodes and asserts all 8 report phase-end events within a bounded time window.
Closest real user-path verification: `docker compose up` for the full rack, then triggering one job through the CLI, observed completing successfully with live metrics visible on the dashboard.
Acceptance gate: the full 8-node rack starts and stays within the 4 gigabyte Linux VM memory budget from section 15 on the reference machine, and one full job completes with all 8 nodes reporting.
Commit boundary: one focused commit for the compose topology and one for the workload runner.
Hardware or external dependency state: none, fully local; this milestone is the first point where the full 8-node rack's memory footprint is verified directly on the reference machine, continuing the per-container measurement started in Milestone 1; if the 4 gigabyte budget is exceeded, apply the 6-node fallback from section 15 and update this milestone's deliverables to the reduced node count before proceeding to Milestone 4.

**Milestone 4, fault injection and straggler ranking, the portfolio-ready core.**
Objective: implement the straggler-ranking algorithm, the fault injector, and the confirmatory statistical evaluation, and reach the portfolio-ready checkpoint.
Deliverables: the MAD z-score algorithm and the naive baseline from section 8, the root-cause tagging logic, the `cpu_contention` and `io_stall` fault injectors from section 11, the frozen `eval/trial_seeds.json` manifest covering both the 80-trial fault-injection batch and the 16-trial no-fault control batch, and `eval/run_trials.py` implementing the full statistical decision contract from section 13, including estimands 1 through 4.
Required tests: the golden, property, metamorphic, and boundary tests for the ranking algorithm from section 8.
Closest real user-path verification: a clean checkout, `docker compose up`, then the documented CLI sequence to start a job with a manually chosen seeded fault, observed correctly flagging the target node in the dashboard's straggler report view.
Acceptance gate, portfolio-ready checkpoint: the clean-checkout manual verification above succeeds; the full predeclared 80-trial fault-injection batch and 16-trial no-fault batch both complete; the exact commit implementing the algorithm and thresholds is tagged `eval-frozen-v1` per the freeze contract in section 13 at that point; and estimands 1, 2, and 3 each report a `PASS`, `FAIL`, or `INSUFFICIENT_EVIDENCE` decision truthfully in `docs/METHODOLOGY.md`, with a `FAIL` on any estimand accepted as a legitimate, honestly reported outcome that still satisfies this gate as long as it is accompanied by the required root-cause analysis of the shortfall.
Commit boundary: one focused commit for the algorithm and its tests, one for the fault injectors and the no-fault control batch, one for the evaluation harness and its first completed trial-batch report tagged `eval-frozen-v1`.
Hardware or external dependency state: none, fully local.

**Milestone 5, extended V1, performance benchmark protocol.**
Objective: execute the full performance contract from section 13 and publish measured results.
Deliverables: the benchmark harness, `docs/PERFORMANCE.md` with the results tables, and the content-addressed raw measurement bundle.
Required tests: a smoke test that the benchmark harness itself runs end to end on a tiny configuration before the full protocol is executed.
Closest real user-path verification: a documented single command reproduces the benchmark harness run, even if a full 5-trial run is not repeated on every invocation.
Acceptance gate: the full protocol from section 13 completes for both configurations, and the secondary performance claims in section 1 are reported as measured, met or not met, never asserted without the corresponding measurement.
Commit boundary: one focused commit.
Hardware or external dependency state: none, fully local.

**Milestone 6, extended V1, debugging timeline and CLI polish.**
Objective: ship the correlated timeline view and finish the `racktl` CLI.
Deliverables: the `GET /api/jobs/{job_id}/timeline/{node_id}` endpoint, its dashboard view, and every `racktl` subcommand listed in section 14.
Required tests: an integration test asserting the timeline endpoint correctly correlates metrics and log lines within the requested window.
Closest real user-path verification: using only `racktl`, a user can start a job, inject a fault, and inspect the timeline for the flagged node without touching the dashboard or raw HTTP calls.
Acceptance gate: every `racktl` subcommand works against a running local rack and the timeline view renders correctly for a completed job.
Commit boundary: one focused commit.
Hardware or external dependency state: none, fully local.

**Milestone 7, extended V1, CI and CD and security hardening.**
Objective: extend the Milestone 1 baseline CI workflow into the full build, test, scan, and image-publishing pipeline.
Deliverables: `.github/workflows/ci.yml` extended from its Milestone 1 baseline to also build and test the Python packages, run the Milestone 2 and Milestone 3 integration tests at a reduced CI-scale trial count, run a container vulnerability scan, and publish built images to GHCR under the user's own namespace tagged with the Git SHA on pushes to `main` only.
Required tests: the CI workflow itself, verified by a real pull request or push triggering a full green run.
Closest real user-path verification: a fresh clone with no local state, run through the exact CI workflow steps, completes successfully.
Acceptance gate: CI passes end to end on a real commit, the vulnerability scan step runs and blocks on high or critical findings, and non-root Dockerfile users are verified for every image.
Commit boundary: one focused commit for the workflow, iterated until green.
Hardware or external dependency state: requires the user's GHCR publishing permission if the image-publish step is enabled; if unavailable, the build and test and scan steps still run and this is reported as a truthful partial completion of this milestone, not a blocker to any other milestone.

**Milestone 8, final release and documentation.**
Objective: finish public documentation and cut the immutable evaluation tag.
Deliverables: `README.md`, `docs/ARCHITECTURE.md`, `docs/METHODOLOGY.md`, `docs/LIMITATIONS.md`, `docs/ALGORITHM_CARD.md`, reproduction instructions, and result tables and screenshots for the interview walkthrough.
Required tests: the complete local verification suite run from a clean checkout.
Closest real user-path verification: a person unfamiliar with the repository follows only `README.md` from a clean clone to a working demonstration.
Acceptance gate: the full clean-checkout acceptance contract in section 19 passes completely.
Commit boundary: one focused commit for documentation, then the `v1.0.0` tag.
Hardware or external dependency state: none, fully local.

## 17. Documentation and Portfolio Evidence

`docs/ARCHITECTURE.md` documents the component table from section 6, the pinned-versions table from section 10, and a system diagram described in text (a simple layered description: node containers, wire protocol, ingestion, storage, analysis, API, dashboard).
`docs/METHODOLOGY.md` documents the algorithm from section 8 and the full statistical decision contract results from section 13, including the honest `PASS`, `FAIL`, or `INSUFFICIENT_EVIDENCE` outcome and, if `FAIL`, the root-cause analysis of the shortfall.
`docs/PERFORMANCE.md` documents the measured results from Milestone 5 against the protocol in section 13.
`docs/LIMITATIONS.md` documents the single-clock-domain limitation, the no-authentication V1 boundary, the absence of any head-to-head benchmark against Netdata, Ganglia, or node_exporter, and every other prohibited claim from section 1.
`docs/ALGORITHM_CARD.md` documents the straggler-ranking algorithm's assumptions, threshold choice, and known failure modes, such as a phase where every node is equally degraded, which the algorithm cannot detect since it ranks relative to the fleet's own median.
The interview walkthrough script in `README.md` follows exactly the primary user workflow in section 2, ending on the straggler report and the reproducible evaluation numbers, so the demonstration is both visually clear and independently reproducible by an interviewer.

## 18. Risks, Kill Gates, and Fallback Claim Tree

| Risk | Likelihood | Impact | Mitigation | Kill gate or fallback |
| --- | --- | --- | --- | --- |
| `libprotobuf` build or link issues inside the Linux C++ image | Low | Medium | Verified directly in Milestone 0 before further build | Fall back to the hand-rolled fixed-width framing format documented in Milestone 0 |
| 8-node rack exceeds the 4 gigabyte Linux VM memory budget on the reference Mac | Medium | Medium | Verified incrementally starting in Milestone 1 and directly in Milestone 3 before Milestone 4 begins | Reduce the reference rack size to 6 nodes (never fewer, to keep at least 5 healthy negative-control nodes clear of the algorithm's own 3-node `INSUFFICIENT_EVIDENCE` floor from section 8) and update every claim and threshold in sections 1 and 13 to match |
| The MAD z-score algorithm fails the confirmatory `PASS` thresholds in section 13 | Medium | Low, since a `FAIL` is a valid documented outcome | Root-cause the shortfall using the naive baseline comparison and the root-cause tagging output | Report the honest `FAIL` with analysis in `docs/METHODOLOGY.md`; this does not block any milestone's acceptance gate |
| Docker Desktop resource limits or thermal throttling on the Mac produce noisy performance numbers | Medium | Low | Thermal-throttle detection and trial discard rule in section 13 | Widen the reported interval and note the limitation explicitly rather than suppressing noisy trials silently |
| GHCR image publishing is unavailable or misconfigured | Low | Low | Milestone 7 treats this as an independently gated sub-step | Ship CI with build, test, and scan only, and report the publish step as a documented, non-blocking gap |
| Scope creep toward a real scheduler, real multi-host deployment, or GPU diagnostics before V1 is done | Medium | Medium | Explicit non-goals in section 5, enforced by the implementation prompt | Any such work is deferred to the follow-on list and never merged into a V1 milestone's acceptance gate |

Fallback claim tree if the primary claim in section 1 cannot reach `PASS` after the full predeclared trial batch: report the measured detection and false-positive rates with their Wilson intervals as the finished result, report the naive-baseline comparison alongside it, and frame the project's demonstrated evidence as "a reproducible, statistically evaluated straggler-ranking method with measured accuracy and a documented false-positive rate," which remains a true, defensible, interview-ready claim even in a `FAIL` outcome, since evaluation rigor itself is significant evidence.

## 19. Final Release and Clean-Checkout Acceptance Contract

Before the `v1.0.0` tag is created, implementation, optimization, documentation, packaging, and the adversarial audit referenced in the workflow that produced this plan must all be complete.

The final `eval/run_trials.py --replay` run in item 5 below executes against the exact tagged source snapshot at `v1.0.0`, which per the freeze contract in section 13 is expected to be the same commit as `eval-frozen-v1` (or a later `eval-frozen-vN` if the algorithm was corrected); results are attached as content-addressed external evidence in `eval/results/` and `docs/METHODOLOGY.md` without further source commits after the tag is created.
Any source change discovered to be necessary after the tagged results are visible requires a new, distinctly named tag, a newly generated seed manifest, and a fresh confirmatory evaluation batch per the `eval-frozen-vN` procedure in section 13; the original tag and its results are never silently overwritten.

Clean-checkout acceptance contract, all of which must pass from a fresh `git clone` with no local state:

1. `docker compose up` brings up the full 8-node rack, ingestion, and dashboard within the 4 gigabyte Linux VM memory budget from section 15 on the reference machine.
2. The documented `racktl` CLI sequence starts a job, injects a fault, and produces a correct straggler report.
3. `ctest` passes for the C++ agent and `pytest` passes for every Python package.
4. The fault-oracle test suite from section 12 passes with every expected reason code and every negative control passing.
5. `eval/run_trials.py --replay` reproduces the committed Milestone 4 trial-batch summary numbers exactly, as a determinism check against the exact `eval-frozen-v1` commit and the frozen seed manifest per the freeze contract in section 13; this is not treated as a fresh confirmatory claim, and if the algorithm changed after `eval-frozen-v1`, this item instead requires the `eval-frozen-v2` fresh batch defined in section 13 to have completed and reported its own decision.
6. The GitHub Actions CI workflow is green on the tagged commit.
7. No placeholder text, no accidental secrets, no restricted data, and no required source file left untracked remain anywhere in the repository.

A blocked, failed, or inconclusive hardware-dependent step is a truthful handoff state and must be reported as such; it is never marked as passing to force a release.

## 20. Authoritative Public Sources

- FastAPI official documentation: `https://fastapi.tiangolo.com`, used for the current API and async usage patterns at implementation time.
- Prometheus `node_exporter` documentation and source: `https://prometheus.io/docs/guides/node-exporter/` and `https://github.com/prometheus/node_exporter`, used to validate that reading hardware and OS metrics from `/proc` and `/sys` is a real, current, standard approach.
- Netdata HPC monitoring solution page: `https://www.netdata.cloud/solutions/use-cases/hpc/`, used as supporting evidence that per-second cluster telemetry is a live operational need.
- "Guard: Scalable Straggler Detection and Node Health Management for Large-Scale Training," arXiv, 2026: `https://arxiv.org/abs/2605.17879`, used as supporting evidence that straggler detection is an active, current, technically substantive problem.
- "AntDT: A Self-Adaptive Distributed Training Framework for Leader and Straggler Nodes," arXiv: `https://arxiv.org/pdf/2404.09679`, used as further supporting evidence for the same claim.
- Iglewicz, B. and Hoya, D., "How to Detect and Handle Outliers," ASQC Quality Press, 1993, the source of the modified z-score method and the 3.5 threshold used in section 8.
- Docker official documentation: `https://docs.docker.com`, used for Dockerfile, Compose, and non-root user best practices at implementation time.
- GitHub Actions official documentation: `https://docs.github.com/actions`, used for the CI and CD workflow implementation at Milestone 7.
- Protocol Buffers official documentation: `https://protobuf.dev`, used for the `.proto` schema design and the C++ and Python code generation workflow.
- SQLite official documentation: `https://www.sqlite.org/docs.html`, used for write-ahead logging configuration and schema design in the storage engine.
