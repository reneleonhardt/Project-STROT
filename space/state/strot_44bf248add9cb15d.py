"""Compiled STROT execution asset. DO NOT EDIT BY HAND.

Synthesized by strot-ai (STROT: Structured Task Reasoning and
Output Transformation, arXiv:2505.01636).

    nlu_model : SupersonicLabs/Julia-1
    runtime   : local
    goal      : Route each consumer-finance complaint to the product it concerns.

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

DATASET_SCHEMA: Dict[str, Any] = {'row_count': 6, 'fields': [{'name': 'text', 'semantic_type': 'text', 'python_type': 'str', 'cardinality': 6, 'null_rate': 0.0, 'sample_values': ['There is a hard inquiry on my Experian report that I never authorized.', 'A collection agency keeps calling about a debt I already paid off two years ago.', 'My credit card issuer charged a late fee even though I paid before the due date.', 'The bank placed a 10-day hold on my check deposit with no explanation.', "My mortgage servicer misapplied my escrow and now says I'm behind on payments."]}]}


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
"""STROT synthesizer output: consumer-finance complaint routing handlers.

Routing decisions are made by the external runtime model. This module provides
deterministic, side-effect-free handler functions that package a routed record
into a JSON-serializable response, plus routing labels and context projection.
"""

from typing import Dict


ROUTING_LABELS: Dict[str, str] = {
    "credit_reporting": "credit report inquiry",
    "debt_collection": "collection agency debt",
    "credit_card": "credit card fee",
    "bank_account": "bank account hold",
    "mortgage": "mortgage escrow servicer",
    "money_transfer": "money transfer wire",
}


def _extract_text(record: dict) -> str:
    """Safely pull the complaint text out of a record."""
    try:
        if not isinstance(record, dict):
            return ""
        value = record.get("text", "")
        if value is None:
            return ""
        return str(value).strip()
    except Exception:
        return ""


def _build_response(record: dict, action: str) -> dict:
    """Assemble a uniform, JSON-serializable routing response."""
    try:
        text = _extract_text(record)
        return {
            "action": action,
            "label": ROUTING_LABELS.get(action, action),
            "text": text,
            "routed": bool(text),
            "status": "ok" if text else "empty_input",
        }
    except Exception as exc:  # pragma: no cover - defensive
        return {
            "action": action,
            "label": ROUTING_LABELS.get(action, action),
            "text": "",
            "routed": False,
            "status": "error",
            "error": str(exc),
        }


def execute_credit_reporting(record: dict) -> dict:
    """Handle action 'credit_reporting'."""
    try:
        return _build_response(record, "credit_reporting")
    except Exception as exc:
        return {"action": "credit_reporting", "status": "error", "error": str(exc)}


def execute_debt_collection(record: dict) -> dict:
    """Handle action 'debt_collection'."""
    try:
        return _build_response(record, "debt_collection")
    except Exception as exc:
        return {"action": "debt_collection", "status": "error", "error": str(exc)}


def execute_credit_card(record: dict) -> dict:
    """Handle action 'credit_card'."""
    try:
        return _build_response(record, "credit_card")
    except Exception as exc:
        return {"action": "credit_card", "status": "error", "error": str(exc)}


def execute_bank_account(record: dict) -> dict:
    """Handle action 'bank_account'."""
    try:
        return _build_response(record, "bank_account")
    except Exception as exc:
        return {"action": "bank_account", "status": "error", "error": str(exc)}


def execute_mortgage(record: dict) -> dict:
    """Handle action 'mortgage'."""
    try:
        return _build_response(record, "mortgage")
    except Exception as exc:
        return {"action": "mortgage", "status": "error", "error": str(exc)}


def execute_money_transfer(record: dict) -> dict:
    """Handle action 'money_transfer'."""
    try:
        return _build_response(record, "money_transfer")
    except Exception as exc:
        return {"action": "money_transfer", "status": "error", "error": str(exc)}


def route_context(record: dict) -> str:
    """Project only the decision-relevant fields into a compact string.

    The only informative field in this schema is the free-text complaint, so we
    return its normalized form for the decision model to classify.
    """
    try:
        text = _extract_text(record)
        if not text:
            return ""
        # Normalize internal whitespace to keep the context compact.
        return " ".join(text.split())
    except Exception:
        return ""

#: Ordered action registry: list position == routing option index.
ACTION_REGISTRY: Dict[str, str] = {'credit_reporting': 'A dispute about a credit report, credit score, or a credit bureau: wrong info, inquiries, identity theft on the report.', 'debt_collection': 'A complaint about a debt collector: collection calls, a debt not owed, harassment, validation of a debt.', 'credit_card': 'A complaint about a credit card: fees, interest, rewards, billing disputes, closed accounts.', 'bank_account': 'A complaint about a checking/savings account: deposits, overdrafts, holds, closures, fraud on the account.', 'mortgage': 'A complaint about a mortgage or home loan: servicing, escrow, modification, foreclosure, payments.', 'money_transfer': 'A complaint about a money transfer, wire, remittance, or digital wallet.'}

_HANDLERS = {'credit_reporting': execute_credit_reporting, 'debt_collection': execute_debt_collection, 'credit_card': execute_credit_card, 'bank_account': execute_bank_account, 'mortgage': execute_mortgage, 'money_transfer': execute_money_transfer}

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
        question: str = 'Which financial product is this complaint about?',
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

