"""Citation checks. The model cites passages as [S1], [S2] (ask) or [N1] (chat).
The harness verifies that every cited label was actually retrieved, flags
sentences with no citation, and measures word overlap between each cited
sentence and its passage as a rough support signal. Overlap is a hint for the
human reviewer, not proof: the evidence cards record a manual check as well."""
from __future__ import annotations

import re

from .retrieval import Hit
from .textutil import tokenize

INSUFFICIENT_MARKERS = ("insufficient evidence", "do not contain", "does not contain",
                        "don't contain", "not enough evidence", "no information")


def is_insufficient(answer: str) -> bool:
    a = answer.lower()
    return any(m in a for m in INSUFFICIENT_MARKERS)


def _sentences(text: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+|\n+", text) if p.strip()]
    merged = []
    for p in parts:
        # "What is IBD? [N4]" splits after "?": glue a citation-only fragment to its sentence.
        if merged and re.match(r"^\[[A-Z]\d", p) and len(tokenize(re.sub(r"\[[^\]]*\]", "", p))) < 3:
            merged[-1] += " " + p
        else:
            merged.append(p)
    return [p for p in merged if len(tokenize(p)) >= 3]


def check(answer: str, hits: list[Hit], prefix: str = "S") -> dict:
    labels = {f"{prefix}{i}": h for i, h in enumerate(hits, 1)}
    pat = re.compile(rf"\[({prefix}\d+(?:\s*,\s*{prefix}\d+)*)\]")
    cited, invalid, per_sentence, uncited = [], [], [], []

    for sent in _sentences(answer):
        found = []
        for m in pat.finditer(sent):
            for lab in re.split(r"\s*,\s*", m.group(1)):
                (found if lab in labels else invalid).append(lab)
        clean = pat.sub("", sent).strip()
        if not found:
            if not is_insufficient(sent) and not clean.endswith(":"):
                uncited.append(clean)
            continue
        words = set(tokenize(clean))
        for lab in found:
            ptoks = set(tokenize(labels[lab].passage.text))
            overlap = round(len(words & ptoks) / len(words), 2) if words else 0.0
            per_sentence.append({"sentence": clean, "label": lab, "overlap": overlap})
            if lab not in cited:
                cited.append(lab)

    return {
        "cited": [{"label": l, "id": labels[l].passage.id, "location": labels[l].passage.location}
                  for l in cited],
        "invalid_labels": sorted(set(invalid)),
        "uncited_sentences": uncited,
        "support": per_sentence,
        "insufficient": is_insufficient(answer),
    }


def summary_lines(result: dict) -> list[str]:
    out = []
    for c in result["cited"]:
        ov = [s["overlap"] for s in result["support"] if s["label"] == c["label"]]
        out.append(f"  [{c['label']}] {c['location']}  (word overlap {max(ov):.0%})")
    if result["invalid_labels"]:
        out.append(f"  ! cited labels that were never retrieved: {', '.join(result['invalid_labels'])}")
    if result["uncited_sentences"]:
        out.append(f"  ! {len(result['uncited_sentences'])} sentence(s) without a citation")
    return out
