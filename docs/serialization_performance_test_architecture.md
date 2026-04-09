# Serialization Performance Test Architecture

## 1) What exists today (quick architecture map)

The project’s serialization surface is concentrated in a few layers:

1. **Model-level JSON serialization/deserialization** via `serialize()` / `deserialize()` wrappers around Pydantic (`model_dump_json` and `model_validate_json`).
2. **Artifact strategy layer** that maps domain models to/from `Part` files:
   - Semantic model: `TmdlStrategy`, `ModelBimStrategy`
   - Report: `PbirStrategy`, `ReportJsonStrategy`
3. **Parser/writer pipeline for TMDL** (`TMDLPartsLoader`, `TMDLPartsWriter`) including lexer/parser/transformer stages.
4. **Transport layer** (`LocalTransport`) for filesystem read/write.

There are already benchmark tests for generic model JSON serialization and TMDL parsing stages, plus CodSpeed CI integration.

---

## 2) Serialization paths that matter most

Prioritize paths by expected runtime impact and developer relevance:

### Tier A (high priority)

1. **TMDL semantic model round-trip**
   - `LocalTransport.read_parts` → `TmdlStrategy.deserialize` (`TMDLPartsLoader.load`) →
     `TmdlStrategy.serialize` (`TMDLPartsWriter.write`) → `LocalTransport.write_parts`
   - Why: main semantic model workflow and largest text payloads.

2. **PBIR report round-trip**
   - `LocalTransport.read_parts` → `PbirStrategy.deserialize` (many JSON files + versioned model dispatch) →
     `PbirStrategy.serialize` → `LocalTransport.write_parts`
   - Why: large fan-out (many small files), regex path matching, many model validations.

3. **Core model JSON encode/decode hot path**
   - `serialize(BaseModel)` and `deserialize(cls, json)`
   - Why: used across strategies and helper conversions.

### Tier B (medium priority)

4. **Format detection overhead** (`detect_semantic_model_format`, `detect_report_format`) on large directories.
5. **Transport-only read/write throughput** with representative part counts and payload sizes.

### Tier C (low priority / diagnostic)

6. **Internal stage benchmarks** (already present for lex/parse/transform/write) for bottleneck diagnosis rather than regression gates.

---

## 3) Separate correctness from performance

Keep two independent suites:

## A. Correctness tests (deterministic, strict)

Purpose: ensure semantic equivalence and compatibility.

- Existing unit/integration round-trip tests remain source of truth.
- Add/ensure assertions for:
  - **Schema-valid decode** for all fixtures.
  - **Semantic equivalence** after round-trip (object comparison or normalized canonical form).
  - **Stability invariants** (e.g., no file loss in PBIR/TMDL parts, expected key files always present).

Do **not** enforce runtime thresholds here.

## B. Benchmark tests (statistical, non-deterministic)

Purpose: measure latency/throughput and detect regressions.

- Mark with `@pytest.mark.benchmark` (or dedicated perf markers).
- Minimize assertions to sanity checks only.
- Isolate from functional test flakiness.

---

## 4) Fixture strategy: realistic + worst-case

Use a small curated fixture catalog under `tests/benchmarks/fixtures/serialization/` with explicit metadata.

## Realistic fixtures

1. **Small semantic model** (already synthetic small model).
2. **Medium semantic model** (existing synthetic large model or scaled-down real sample).
3. **Large real-world semantic model** (AI sample already in tree).
4. **Large real-world PBIR report** (AI sample report already in tree).

## Worst-case fixtures

Add generated fixtures (scripted, deterministic) that target pathological behaviors:

1. **Deep expression complexity**
   - Long multiline expressions, many measures/columns.
2. **High file-count PBIR**
   - Thousands of tiny visual/mobile JSON files to stress path matching + object init overhead.
3. **Large single-file model.bim**
   - Very large JSON payload to stress `model_validate_json`.
4. **Many optional/null-like fields toggled**
   - Stress model construction and dump filtering (`exclude_none=True`).

Implementation note: generate these once via script and commit compact-but-representative versions to avoid heavy CI setup.

---

## 5) Benchmark scenario matrix

For each fixture, benchmark these scenario types:

1. **Deserialize-only**
   - from parts/json into domain model.
2. **Serialize-only**
   - from model to parts/json.
3. **Round-trip in-memory**
   - deserialize + serialize, no disk writes.
4. **Round-trip with transport**
   - include read/write `LocalTransport` for end-to-end latency.

Recommended naming convention:

- `bench_semantic_tmdl_deserialize_<fixture>`
- `bench_semantic_tmdl_serialize_<fixture>`
- `bench_semantic_tmdl_roundtrip_mem_<fixture>`
- `bench_semantic_tmdl_roundtrip_io_<fixture>`
- `bench_report_pbir_deserialize_<fixture>`
- `bench_report_pbir_serialize_<fixture>`
- `bench_report_pbir_roundtrip_mem_<fixture>`
- `bench_report_pbir_roundtrip_io_<fixture>`
- `bench_core_json_{serialize|deserialize}_<fixture>`

---

## 6) Repeatable benchmark design for local + CI

Use two benchmark tiers:

## Tier 1: PR/CI “guardrail” benchmarks

- Small/medium fixtures only.
- Fixed iterations/min rounds tuned for <5 minutes total.
- Run under CodSpeed (`--codspeed`) in CI.
- Trigger regression alerts with moderate thresholds.

## Tier 2: Nightly/deep benchmarks

- Includes largest realistic + worst-case fixtures.
- More repetitions for tighter confidence.
- Produces detailed trend data but does not block routine PRs unless severe.

Practical pytest-benchmark settings (example profile):

- `--benchmark-warmup=on`
- `--benchmark-min-rounds=8` (PR) / `20` (nightly)
- `--benchmark-disable-gc` for CPU-focused microbenchmarks (selectively)
- Pin environment where possible (runner type, Python version)

For local runs, expose shortcuts (documented commands):

- `uv run pytest tests/benchmarks -m benchmark`
- `uv run pytest tests/benchmarks -m benchmark --benchmark-sort=mean`
- `uv run pytest tests/perf/test_tmdl_parsing_perf.py -k roundtrip`

---

## 7) Baselines and regression thresholds

Use baseline-per-benchmark with explicit policy:

1. **Baseline source**
   - CodSpeed historical baseline on `main` for CI.
   - Optional checked-in local baseline JSON for reproducible developer comparison.

2. **Regression thresholds (initial practical defaults)**
   - **PR guardrail benchmarks**:
     - warn at **+10%** mean regression,
     - fail at **+20%** regression on Tier A scenarios.
   - **Nightly benchmarks**:
     - warn at **+7%**, fail at **+15%** for high-confidence runs.

3. **Noise handling**
   - Require regression in at least 2 consecutive CI runs before hard-fail for non-critical paths.
   - For known noisy I/O scenarios, use broader thresholds than in-memory scenarios.

4. **Change management**
   - Permit baseline reset only via explicit PR note: “expected perf shift” with rationale.

---

## 8) Monitoring over time

Use CodSpeed as primary trend monitor, grouped by scenario tags:

- `semantic/tmdl/*`
- `report/pbir/*`
- `core/json/*`
- `transport/io/*`

Operational policy:

1. Track p50 and mean trends weekly.
2. Annotate major parser/model changes with expected perf impact.
3. If trend degrades >15% over 4 weeks, open perf-investigation issue.

Optional: produce a compact Markdown summary artifact in CI with top regressions/improvements and link it from PR comments.

---

## 9) Proposed repository structure (simple to maintain)

```text
tests/
  benchmarks/
    test_serialization_core.py         # current + expanded core JSON benches
    test_semantic_tmdl_bench.py        # semantic model deserialize/serialize/roundtrip
    test_report_pbir_bench.py          # report deserialize/serialize/roundtrip
    fixtures/
      serialization/
        realistic/
        worst_case/
    conftest.py                        # shared fixture loaders + benchmark helpers
scripts/
  generate_serialization_fixtures.py   # deterministic worst-case fixture generator
```

Keep benchmark helper utilities minimal and colocated in `tests/benchmarks/conftest.py`.

---

## 10) Implementation plan (incremental)

1. **Phase 1 (fast win)**
   - Split benchmark files by domain (core/tmdl/pbir).
   - Add scenario naming + fixture metadata.
   - Keep current fixtures, enable CI guardrails on Tier A critical scenarios.

2. **Phase 2**
   - Add deterministic worst-case fixture generator and commit generated fixtures.
   - Introduce nightly benchmark workflow.

3. **Phase 3**
   - Add automated regression summary report and threshold policy refinements.

This sequencing delivers immediate value with low maintenance cost, then scales to deeper performance observability.
