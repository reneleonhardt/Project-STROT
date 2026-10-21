---
title: STROT — Decision Compiler
emoji: ⚙️
colorFrom: purple
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# STROT — live demo

An LLM compiles your intent once into a frozen pipeline. After that, a small
local model (SupersonicLabs/Julia-1, 144M) makes every decision on CPU — no LLM
call, no API key, ~60ms per record, bounded typed-JSON output with confidence.
Low-confidence records abstain instead of guessing.

- **Try it** runs records through pre-compiled artifacts. This is the runtime:
  key-free, CPU-only, $0 per decision.
- **Compile your own** uses your API key once to build a fresh artifact.

Source: https://github.com/strot-ai/STROT-Compiler · `pip install strot-ai`
