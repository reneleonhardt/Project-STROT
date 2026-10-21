"""Build-time pre-compilation of the demo artifacts.

Runs once, during the Docker build, with an Anthropic key supplied as a build
secret. Compiles each demo task into a frozen artifact under STROT_STATE so the
running Space can serve decisions with no LLM call and no API key.

If no key is present the script exits quietly; the app then falls back to the
"Compile your own" tab only.
"""

import os
import sys

import strot

from demo_tasks import TASKS

STATE = os.environ.get("STROT_STATE", "/app/state")
LLM = "anthropic/claude-opus-4-8"

if not os.environ.get("ANTHROPIC_API_KEY"):
    print("precompile: no ANTHROPIC_API_KEY, skipping (BYO-key tab only).")
    sys.exit(0)

for key, task in TASKS.items():
    sample = [{"text": t} for t in task["examples"]]
    print(f"precompile: compiling '{key}' ...", flush=True)
    try:
        strot.run(
            sample,
            query=task["query"],
            action_registry=task["registry"],
            question=task["question"],
            llm=LLM,
            state=STATE,
            sample_size=len(sample),
            measure_labels=True,
        )
        print(f"precompile: '{key}' compiled -> {STATE}", flush=True)
    except Exception as exc:  # noqa: BLE001 - one bad task shouldn't fail the build
        print(f"precompile: '{key}' FAILED: {type(exc).__name__}: {exc}", flush=True)
