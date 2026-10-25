"""Compiled STROT execution asset. DO NOT EDIT BY HAND.

Synthesized by strot-ai (STROT: Structured Task Reasoning and
Output Transformation, arXiv:2505.01636).

    nlu_model : SupersonicLabs/Julia-1
    runtime   : local
    goal      : Triage incoming support tickets into the correct workflow.

This file is completely self-contained (zero strot-package imports) and
can be dropped into any production pipeline as-is.
"""

import json
import math
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence

NLU_MODEL = 'SupersonicLabs/Julia-1'
CONFIDENCE_THRESHOLD = 0.4
MAX_FLAT_OPTIONS = 20

#: Fitted at compile time from teacher-labeled sample records (None = uncalibrated).
TEMPERATURE: float = 1.0
CONFORMAL_Q = None
CALIBRATION: Dict[str, Any] = {}
CLASS_BIAS = None
DISPATCH_CUTOFF = None
POLICY: Dict[str, Any] = {}

DATASET_SCHEMA: Dict[str, Any] = {'row_count': 5, 'fields': [{'name': 'text', 'semantic_type': 'text', 'python_type': 'str', 'cardinality': 5, 'null_rate': 0.0, 'sample_values': ['I was charged twice for the same subscription this month, please refund one.', 'The app crashes every time I open the reports page on Android.', "I can't log in, it says my account is locked after too many attempts.", 'My invoice shows the wrong tax amount for my region.', "Export to CSV produces an empty file since yesterday's update."]}]}


class FallbackException(Exception):
    """Low-confidence routing refusal: do not execute any path blindly."""

    def __init__(self, message: str, confidence: float, threshold: float) -> None:
        super().__init__(message)
        self.confidence = confidence
        self.threshold = threshold


@dataclass(frozen=True)
class RouteDecision:
    index: int
    option: str
    confidence: float
    distribution: Dict[str, float] = field(default_factory=dict)


# --- Runtime architecture: Implementation Alpha (local Julia decision model) ---
# Julia is NOT a Transformers AutoModel; it ships its own inference package
# ("supersonic-julia") inside the checkpoint repository.
try:
    from julia import load_model
except ImportError as _exc:  # pragma: no cover - environment guard
    raise RuntimeError(
        "This compiled asset routes locally with SupersonicLabs/Julia-1 and needs the "
        "'supersonic-julia' package (do NOT `pip install julia` - that is an "
        "unrelated package). Install:\n"
        "  python -c \"from huggingface_hub import snapshot_download; "
        "snapshot_download('SupersonicLabs/Julia-1', local_dir='Julia-1')\"\n"
        "  pip install ./Julia-1"
    ) from _exc


class _RuntimeRouter:
    """Resident Julia decision engine over SupersonicLabs/Julia-1 on CPU."""

    def __init__(self) -> None:
        checkpoint = os.environ.get("STROT_NLU_CHECKPOINT")
        if checkpoint is None:
            from pathlib import Path

            if Path(NLU_MODEL).is_dir():
                checkpoint = NLU_MODEL
            else:
                from huggingface_hub import snapshot_download

                checkpoint = snapshot_download(NLU_MODEL)
        self._engine = load_model(checkpoint, device="cpu")

    def select(self, context: str, question: str, options: Sequence[str]) -> RouteDecision:
        if len(options) == 1:  # Julia accepts 2-20 options; one action is trivial
            return RouteDecision(0, options[0], 1.0, {options[0]: 1.0})
        if len(options) <= MAX_FLAT_OPTIONS:
            return self._select_flat(context, question, options)
        return self._select_hierarchical(context, question, options)

    def _select_hierarchical(
        self, context: str, question: str, options: Sequence[str]
    ) -> RouteDecision:
        # Option Tree Splitter: Julia-1 accuracy degrades beyond 20 choices,
        # so oversized registries route through a multi-tier decision tree.
        n_groups = math.ceil(len(options) / MAX_FLAT_OPTIONS)
        size = math.ceil(len(options) / n_groups)
        groups = [list(options[i : i + size]) for i in range(0, len(options), size)]
        labels = [
            "Options {0}-{1}: {2} ... {3}".format(
                list(options).index(g[0]) + 1, list(options).index(g[-1]) + 1, g[0], g[-1]
            )
            for g in groups
        ]
        branch = self.select(
            context, question + " (choose the group containing the best option)", labels
        )
        leaf = self.select(context, question, groups[branch.index])
        winner = groups[branch.index][leaf.index]
        return RouteDecision(
            index=list(options).index(winner),
            option=winner,
            confidence=branch.confidence * leaf.confidence,
            distribution=dict(leaf.distribution),
        )

    def _select_flat(self, context: str, question: str, options: Sequence[str]) -> RouteDecision:
        result = self._engine.predict(
            rows=[{"state": context, "question": question, "options": list(options)}]
        )[0]
        index = int(result["index"])
        probs = [float(p) for p in result["probabilities"]]
        return RouteDecision(
            index=index,
            option=options[index],
            confidence=probs[index],
            distribution=dict(zip(options, probs)),
        )


# --- Statically generated execution paths (STROT synthesizer output) ---
from typing import Dict, Any


ROUTING_LABELS: Dict[str, str] = {
    "billing_dispute": "charged refund invoice",
    "technical_defect": "crashes bug error",
    "account_access": "login account locked",
}


def _safe_text(record: dict) -> str:
    """Extract and normalize the 'text' field from a record."""
    try:
        value = record.get("text", "")
        if value is None:
            return ""
        return str(value).strip()
    except Exception:
        return ""


def execute_billing_dispute(record: dict) -> dict:
    """Handle a billing-related support ticket (refunds, invoice corrections,
    double charges, billing questions)."""
    try:
        text = _safe_text(record)
        return {
            "action": "billing_dispute",
            "status": "routed",
            "workflow": "billing",
            "queue": "finance_support",
            "priority": "high",
            "requires_refund_review": True,
            "ticket_text": text,
            "next_steps": [
                "Verify the customer's billing history and recent charges.",
                "Confirm duplicate charges, incorrect taxes, or invoice errors.",
                "Issue refund or invoice correction if validated.",
            ],
        }
    except Exception as exc:
        return {
            "action": "billing_dispute",
            "status": "error",
            "error": str(exc),
        }


def execute_technical_defect(record: dict) -> dict:
    """Handle a technical defect support ticket (crashes, bugs, errors,
    broken or unexpected behavior)."""
    try:
        text = _safe_text(record)
        return {
            "action": "technical_defect",
            "status": "routed",
            "workflow": "engineering",
            "queue": "technical_support",
            "priority": "high",
            "requires_bug_report": True,
            "ticket_text": text,
            "next_steps": [
                "Reproduce the reported behavior and capture logs.",
                "Identify affected platform, version, or feature.",
                "File or link a defect ticket for engineering triage.",
            ],
        }
    except Exception as exc:
        return {
            "action": "technical_defect",
            "status": "error",
            "error": str(exc),
        }


def execute_account_access(record: dict) -> dict:
    """Handle an account access support ticket (login problems, password
    resets, locked or suspended accounts)."""
    try:
        text = _safe_text(record)
        return {
            "action": "account_access",
            "status": "routed",
            "workflow": "identity",
            "queue": "account_support",
            "priority": "high",
            "requires_identity_verification": True,
            "ticket_text": text,
            "next_steps": [
                "Verify the customer's identity before any account change.",
                "Check for lockouts, suspensions, or failed login attempts.",
                "Unlock the account or initiate a secure password reset.",
            ],
        }
    except Exception as exc:
        return {
            "action": "account_access",
            "status": "error",
            "error": str(exc),
        }


def route_context(record: dict) -> str:
    """Project only the decision-relevant fields into a compact string for the
    runtime decision model. Only the ticket text drives routing here."""
    try:
        text = _safe_text(record)
        if not text:
            return "text: (empty)"
        return f"text: {text}"
    except Exception:
        return "text: (unavailable)"

#: Ordered action registry: list position == routing option index.
ACTION_REGISTRY: Dict[str, str] = {'billing_dispute': 'Refunds, invoice corrections, double charges, billing questions.', 'technical_defect': 'Crashes, bugs, errors, broken or unexpected behavior.', 'account_access': 'Login problems, password resets, locked or suspended accounts.'}

_HANDLERS = {'billing_dispute': execute_billing_dispute, 'technical_defect': execute_technical_defect, 'account_access': execute_account_access}

#: The decision model sees ONLY these compile-time-synthesized labels;
#: short discriminative labels measurably outperform verbose descriptions.
_ROUTING_OPTIONS: List[str] = [ROUTING_LABELS[key] for key in ACTION_REGISTRY]
_ACTION_KEYS: List[str] = list(ACTION_REGISTRY)


class CompiledPipeline:
    """Self-routing execution asset: route each record, enforce confidence,
    dispatch to the statically compiled path."""

    def __init__(self) -> None:
        self._router = _RuntimeRouter()

    def process(
        self,
        record: Mapping[str, Any],
        question: str = 'Which workflow should handle this ticket?',
    ) -> Dict[str, Any]:
        context = route_context(dict(record))  # compile-time-synthesized projection
        decision = self._router.select(context, question, _ROUTING_OPTIONS)
        # Inference-level correction (fitted at compile): temperature +
        # per-class bias over the arbiter's distribution.
        raw = [
            max(decision.distribution.get(opt, 0.0), 1e-12)
            for opt in _ROUTING_OPTIONS
        ]
        scores = [
            math.log(p) / TEMPERATURE + (CLASS_BIAS[i] if CLASS_BIAS else 0.0)
            for i, p in enumerate(raw)
        ]
        peak = max(scores)
        exps = [math.exp(s - peak) for s in scores]
        total = sum(exps)
        probs = [e / total for e in exps]

        index = max(range(len(probs)), key=probs.__getitem__)
        confidence = probs[index]
        abstain_reason = None
        if CONFORMAL_Q is not None:
            included = [i for i, p in enumerate(probs) if p >= 1.0 - CONFORMAL_Q]
            if len(included) == 1:
                index = included[0]
                confidence = probs[index]
            else:
                abstain_reason = (
                    "Conformal prediction set holds {0} labels (needs exactly "
                    "1 to dispatch at alpha={1})".format(
                        len(included), CALIBRATION.get("alpha")
                    )
                )
        elif DISPATCH_CUTOFF is not None:
            if confidence < DISPATCH_CUTOFF:
                abstain_reason = (
                    "Corrected confidence {0:.3f} below the fitted dispatch "
                    "cutoff {1:.3f} (target accuracy {2})".format(
                        confidence, DISPATCH_CUTOFF, POLICY.get("target_accuracy")
                    )
                )
        else:
            if decision.confidence < CONFIDENCE_THRESHOLD:
                abstain_reason = (
                    "Routing confidence {0:.3f} below threshold {1:.2f}".format(
                        decision.confidence, CONFIDENCE_THRESHOLD
                    )
                )
            else:
                index = decision.index
                confidence = decision.confidence

        if abstain_reason is None:
            action_key = _ACTION_KEYS[index]
            result = _HANDLERS[action_key](dict(record))
            return {
                "action": action_key,
                "confidence": confidence,
                "result": result,
            }

        raise FallbackException(
            abstain_reason + "; falling back.",
            confidence=confidence,
            threshold=DISPATCH_CUTOFF or CONFIDENCE_THRESHOLD,
        )


if __name__ == "__main__":
    import sys

    pipeline = CompiledPipeline()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            print(json.dumps(pipeline.process(json.loads(line)), default=str))
        except FallbackException as exc:
            print(json.dumps({"action": None, "error": str(exc)}))

