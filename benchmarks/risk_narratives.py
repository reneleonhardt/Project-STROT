"""Risk-narrative benchmarks: STROT on real, unstructured, record-level text.

Two fully public, ground-truth-labeled decision tasks that match STROT's actual
strength (categorical triage/taxonomy over free text), not subtle sentiment:

  CYBER    VERIS Community Database (vz-risk/VCDB) incident summaries ->
           attack action category (hacking/malware/error/misuse/physical/social)
  FINANCE  CFPB consumer-complaint narratives -> product category

Both are class-balanced so accuracy is interpretable, and every task prints the
random and majority-class baselines next to the scores. No human labeling: the
labels ship with the data; STROT never sees the test labels.

naive    = raw narrative + bare class names into the decision model
compiled = strot.run (compiler synthesizes labels + projection, measures which
           labeling wins on a teacher-labeled sample, calibrates, gates)
"""

import collections
import io
import json
import time
import urllib.request
import zipfile

import strot
from julia import load_model

engine = load_model("/opt/julia-1", device="cpu")
HF = "https://datasets-server.huggingface.co/rows?dataset={d}&config={c}&split={s}&offset={o}&length=100"
VCDB_ZIP = "https://github.com/vz-risk/VCDB/raw/master/data/joined/vcdb.json.zip"
CAP = 25            # records per class (balanced)
SAMPLE_PER = 6      # compile-sample records per class


def _get(url, timeout=90):
    for attempt in range(5):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return r.read()
        except Exception:
            if attempt == 4:
                raise
            time.sleep(8 * (attempt + 1))


def balance(items, label_of, text_of, classes, cap, sample_per):
    """Bucket by class, keep <=cap per class; split front `sample_per` as the
    compile sample, remainder as test. Returns (sample_texts, test_texts, test_truth)."""
    buckets = collections.defaultdict(list)
    for it in items:
        lab = label_of(it)
        if lab in classes and isinstance(text_of(it), str) and len(text_of(it).strip()) > 40:
            if len(buckets[lab]) < cap:
                buckets[lab].append(text_of(it).strip())
    idx = {c: i for i, c in enumerate(classes)}
    s_texts, t_texts, t_truth = [], [], []
    for c in classes:
        rows = buckets[c]
        s_texts += rows[:sample_per]
        for r in rows[sample_per:]:
            t_texts.append(r)
            t_truth.append(idx[c])
    return s_texts, t_texts, t_truth, {c: len(buckets[c]) for c in classes}


def baselines(truth, n_classes):
    maj = collections.Counter(truth).most_common(1)[0][1] / len(truth)
    return round(100 / n_classes, 1), round(maj * 100, 1)


def naive_acc(texts, truth, names, question):
    correct = 0
    for i in range(0, len(texts), 50):
        rows = [{"state": t[:1500], "question": question, "options": names} for t in texts[i:i + 50]]
        for res, tr in zip(engine.predict(rows=rows), truth[i:i + 50]):
            correct += int(res["index"]) == tr
    return round(correct / len(texts) * 100, 1)


def compiled_acc(name, sample_texts, test_texts, truth, registry, query, question, idx):
    sample = [{"text": t[:1500]} for t in sample_texts]
    records = [{"text": t[:1500]} for t in test_texts]
    off = len(sample)
    result = strot.run(sample + records, query, registry,
                       question=question, measure_labels=True,
                       llm="anthropic/claude-opus-4-8", state=f"/tmp/risk_{name}",
                       sample_size=len(sample))
    routed = {o["index"]: o["action"] for o in result.outcomes}
    correct = sum(1 for i, tr in enumerate(truth)
                  if routed.get(i + off) is not None and idx[routed[i + off]] == tr)
    fb = sum(1 for f in result.fallbacks if f["index"] >= off)
    return round(correct / len(truth) * 100, 1), fb, result.attempts


def run_task(title, loader):
    print(f"\n================ {title} ================", flush=True)
    try:
        names, question, query, reg, idx, s_tx, t_tx, truth, counts = loader()
        rnd, maj = baselines(truth, len(names))
        print(f"classes: {counts}")
        print(f"test records: {len(t_tx)}   random baseline: {rnd}%   majority baseline: {maj}%")
        print(f"naive:    {naive_acc(t_tx, truth, names, question)}%", flush=True)
        a, fb, at = compiled_acc(title.split(":")[0].strip().lower()[:8],
                                 s_tx, t_tx, truth, reg, query, question, idx)
        print(f"compiled: {a}%  (fallbacks {fb}, attempts {at})")
    except Exception as exc:
        import traceback
        print(f"SKIPPED: {type(exc).__name__}: {str(exc)[:200]}")
        traceback.print_exc()


def cyber_vcdb():
    data = json.loads(zipfile.ZipFile(io.BytesIO(_get(VCDB_ZIP))).read("vcdb_1-of-1.json"))
    classes = ["hacking", "malware", "error", "misuse", "physical", "social"]

    def label(r):
        acts = [a for a in r.get("action", {}) if a in classes]
        return acts[0] if len(acts) == 1 else None

    s_tx, t_tx, truth, counts = balance(data, label, lambda r: r.get("summary"),
                                        classes, CAP, SAMPLE_PER)
    reg = {
        "hacking": "Intrusion via technical means: stolen/brute-forced credentials, exploited vulnerabilities, SQL injection, remote access.",
        "malware": "Malicious software: ransomware, spyware, trojans, keyloggers, worms installed on a system.",
        "error": "Unintentional mistake: misdelivery, misconfiguration, lost device, accidental publishing or disposal of data.",
        "misuse": "Authorized insider abusing access: snooping, data theft by staff, policy violation.",
        "physical": "Physical action: theft of a device/document, tampering, surveillance, break-in.",
        "social": "Social engineering of a person: phishing, pretexting, bribery, deception.",
    }
    return (classes, "What was the primary attack action in this security incident?",
            "Classify each security-incident report by its primary attack action.",
            reg, {c: i for i, c in enumerate(classes)}, s_tx, t_tx, truth, counts)


def finance_cfpb():
    rows = []
    for off in range(0, 9000, 100):
        rows += [x["row"] for x in json.loads(_get(HF.format(
            d="claritystorm/cfpb-consumer-complaints", c="default", s="train", o=off)))["rows"]]
        if len(rows) >= 9000:
            break
    canon = {
        "Credit reporting or other personal consumer reports": "credit_reporting",
        "Credit reporting / repair": "credit_reporting",
        "Debt collection": "debt_collection",
        "Credit card": "credit_card",
        "Bank account / service": "bank_account",
        "Mortgage": "mortgage",
        "Money transfer / service": "money_transfer",
    }
    classes = ["credit_reporting", "debt_collection", "credit_card",
               "bank_account", "mortgage", "money_transfer"]

    def label(r):
        return canon.get(r.get("product_normalised") or r.get("product"))

    s_tx, t_tx, truth, counts = balance(rows, label, lambda r: r.get("consumer_narrative"),
                                        classes, CAP, SAMPLE_PER)
    reg = {
        "credit_reporting": "A dispute about a credit report, credit score, or a credit bureau (Experian/Equifax/TransUnion): wrong info, inquiries, identity theft on the report.",
        "debt_collection": "A complaint about a debt collector: collection calls, a debt the consumer doesn't owe, harassment, validation of a debt.",
        "credit_card": "A complaint about a credit card: fees, interest, rewards, billing disputes, closed accounts.",
        "bank_account": "A complaint about a checking/savings bank account: deposits, overdrafts, holds, account closures, fraud on the account.",
        "mortgage": "A complaint about a mortgage or home loan: servicing, escrow, modification, foreclosure, payments.",
        "money_transfer": "A complaint about a money transfer, wire, remittance, or digital wallet.",
    }
    return (classes, "Which financial product is this consumer complaint about?",
            "Route each consumer-finance complaint to the product it concerns.",
            reg, {c: i for i, c in enumerate(classes)}, s_tx, t_tx, truth, counts)


run_task("CYBER: VCDB incident -> attack action", cyber_vcdb)
run_task("FINANCE: CFPB complaint -> product", finance_cfpb)
