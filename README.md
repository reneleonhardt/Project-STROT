<div align="center">

# ⬢ STROT

### The open decision compiler

**Compile your intent once with an LLM. Then decide on every record forever** —
classification, scoring, routing — as type-safe JSON with probabilities and
confidence, on your own hardware, at **zero marginal cost**.

[![PyPI](https://img.shields.io/pypi/v/strot-ai?color=7c3aed&label=pip%20install%20strot-ai)](https://pypi.org/project/strot-ai/)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-106%20passing-brightgreen)](tests/)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](pyproject.toml)

[**Website**](https://strot.ai) · [**Docs**](DEVELOPERS.md) · [**Benchmarks**](benchmarks/) · [**PyPI**](https://pypi.org/project/strot-ai/)

```
Agents at compile time.  Never at runtime.
```

</div>

---

```bash
pip install strot-ai
```

```python
import strot

result = strot.run(
    tickets,
    query="Triage incoming support tickets into the correct workflow.",
    action_registry={
        "billing_dispute":  "Refunds, invoice corrections, double charges",
        "technical_defect": "Crashes, bugs, broken behavior",
    },
    llm="anthropic/claude-opus-4-8",   # used once, on first compile only
)

for o in result.outcomes:
    print(o["action"], round(o["confidence"], 2))
# billing_dispute 0.97
# technical_defect 0.94
```

The LLM runs **once**, at compile time. Production is a frozen, self-contained
Python artifact: a small local decision model arbitrates every record, nothing
is generated, every output is bounded, and low-confidence records abstain
instead of guessing.

<div align="center">

```
STROT = Agentic Schema Intent + Compiler & State + Code + Execution + NLU
                      ⟹  JSON Decisions
          (classification · scoring · routing · typed answers)
```

</div>

## How it works

```
            COMPILE  (once per intent + schema)
  intent + sample ─▶ synthesize ─▶ golden gate ─▶ teacher labels ─▶ calibrate
                     (labels,      (your known      (annotate         (fit the
                      projection,   answers must     a sample,         confidence
                      handlers)     pass)            once)             threshold)
                                        │
                                        ▼
                             frozen artifact  (.py)

            RUNTIME  (every record, forever)
  record ─▶ projection ─▶ decision model ─▶ confidence gate ─▶ typed JSON
            (compiled)     (144M, CPU,        (decide or         decision
                            ~60 ms)            abstain)
```

## Two surfaces

**`run()`** — route each record to an action and execute the compiled handler.

**`decide()`** — answer typed questions (choice / score / boolean) per record:

```python
result = strot.decide(records, questions={
    "is_bug_report":     {"type": "boolean", "instructions": "mentions crashes/errors?"},
    "customer_sentiment":{"type": "score", "min": 1, "max": 5, "instructions": "1 angry, 5 happy"},
    "routing_bucket":    {"type": "choice", "options": ["billing", "engineering", "spam"]},
})
# → {"booleans": {...}, "scores": {...}, "choices": {...}}  with probabilities + confidence
```

## Measured

Real model (SupersonicLabs/Julia-1, 144M, CPU), real datasets, clean Docker containers:

| | Result |
|---|---|
| Grounded routing accuracy (398 records) | **92.5%** compiled vs 74.8% naive — the compiler is worth +18pp on the same model |
| Semantic text (AG News, unseen labels) | **86.7%** compiled vs 72.7% naive (+14pp) |
| Typed decisions vs the leading hosted decision API's own example | near-identical (sentiment 1.79 vs 1.8) |
| Latency / marginal cost / LLM calls per record | **~60 ms · $0 · 0** |

Reproduce everything: [`benchmarks/`](benchmarks/) — with the losses published too.

### On real risk narratives

Record-level, unstructured text — the kind cyber, financial, and insurance
triage actually runs on. Fully public, ground-truth datasets; classes balanced
so accuracy is interpretable; baselines shown; nothing is hand-labeled and STROT
never sees the test labels. ([`benchmarks/risk_narratives.py`](benchmarks/risk_narratives.py))

| Task — 6-class, balanced | Random | Majority | Naive | Compiled | Abstains |
|---|---|---|---|---|---|
| **Cyber** — [VERIS/VCDB](https://github.com/vz-risk/VCDB) incident note → attack action | 16.7% | 16.7% | 36.8% | **39.5%** | 8/114 |
| **Finance** — [CFPB](https://www.consumerfinance.gov/data-research/consumer-complaints/) complaint → product | 16.7% | 26.4% | 54.2% | **61.1%** | 5/72 |

Both clear their baselines, the compiler lifts accuracy on the *same* 144M local
model (+2.7pp / +6.9pp), and low-confidence records abstain instead of guessing.
These are honest proof the architecture works on messy real narratives — not
production underwriting accuracy. For that, drop a task-trained specialist in the
`nlu=` slot; the compiler, calibration, and gate are unchanged.

## What makes it different

- **Compile once, decide forever** — content-addressed artifact cache; schema drift triggers exactly one recompile.
- **Golden-record promotion** — artifacts must pass your known answers before they serve.
- **Fitted guarantees** — temperature scaling + split conformal prediction, baked in: dispatched decisions are wrong ≤ α of all records (marginal); the rest abstain.
- **Measured, not guessed** — the compiler scores labelings, and can train a distilled head, keeping only what beats the baseline on held-out data.
- **0% structural hallucination** — output is selection + computation over your registry; nothing is generated at runtime.
- **Model-independent** — the decision model is a slot (`nlu=`): local Julia-1 by default, hosted APIs, or any drop-in specialist.

## Install

```bash
pip install strot-ai            # core: pure stdlib
pip install strot-ai[local]     # + the local decision model (torch/transformers)
pip install strot-ai[hosted]    # + openai, for a hosted decision runtime
pip install strot-ai[anthropic] # + anthropic, for the synthesizer
```

Bake the local model into your image for offline production:

```dockerfile
RUN pip install strot-ai[local] \
 && python -c "import strot; strot.prefetch_nlu(local_dir='/opt/julia-1', install=True)"
ENV STROT_NLU_CHECKPOINT=/opt/julia-1
```

(Never `pip install julia` — unrelated package.)

## Documentation

[**DEVELOPERS.md**](DEVELOPERS.md) — architecture, compile lifecycle, calibration
semantics and caveats, deployment, model swapping, full API reference.

## License

MIT. Default decision model: Apache-2.0 ([SupersonicLabs/Julia-1](https://huggingface.co/SupersonicLabs/Julia-1)). Implements ideas from STROT (arXiv:2505.01636).
