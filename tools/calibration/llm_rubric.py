#!/usr/bin/env python3
"""AI as a MEASURING TOOL (2026-10-26; owner: "theres definitely ways to boost party prediction accuracy using llms
... dig deeper"). Literature: LLMs work best as a measurement device whose outputs an ordinary model learns to use
(docs/research/legislator_vote_prediction_survey.md, section C.4). The AI reads ONLY the blinded official summary
AS INTRODUCED (LIS Summaries.csv, authorized 2025/2026, cached by historical_cache/fetch.py) and fills a fixed
checklist. No room, no tallies, no names -> no cross-bill leak. INTERNAL ONLY (text-derived, Standard #3).
Modes:  build   blinded items for every first-voted 2025 / 2026 bill, packed 60 per file (.cache/llm_rubric/)
        load    -> dict (session, bill) -> checklist   (used by rubric_eval.py)
"""
from __future__ import annotations
import sys, os, re, io, csv, gzip, json, random, collections, html
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
OUT = os.path.join(HERE, ".cache", "llm_rubric")
CACHE = os.path.join(HERE, "..", "historical_cache", "va")


def introduced():
    """(session, 'HB 9') -> summary-as-introduced text (HTML stripped)."""
    out = {}
    for code, ses in (("20251", "2025"), ("20261", "2026")):
        t = gzip.open(os.path.join(CACHE, code, "Summaries.csv.gz"), "rt", encoding="utf-8", errors="replace").read()
        for r in csv.DictReader(io.StringIO(t)):
            if r["SUMMARY_TYPE"].strip() != "SUMMARY AS INTRODUCED":
                continue
            m = re.match(r"([A-Z]+)0*(\d+)", r["SUM_BILNO"].strip())
            txt = html.unescape(re.sub(r"<[^>]+>", " ", r["SUMMARY_TEXT"]))
            out[(ses, f"{m.group(1)} {m.group(2)}")] = re.sub(r"\s+", " ", txt).strip()
    return out


def build():
    import gains as G, llm_member as M
    summ = introduced(); items = []; missing = collections.Counter()
    for split, yr in (("confirm", "2025"), ("repeat", "2026")):
        te, _a, _b = G.load(split)
        for k in sorted({tuple(r["bill"]) for r in te}):
            if k in summ:
                items.append((k, M.blind(summ[k])[:1500]))
            else:
                missing[yr] += 1                                   # counted and printed
    rng = random.Random(26); rng.shuffle(items)
    ids = {f"R{i:04d}": list(k) for i, (k, _t) in enumerate(items)}
    os.makedirs(OUT, exist_ok=True); json.dump(ids, open(os.path.join(OUT, "ids.json"), "w"))
    for f in range(0, len(items), 60):
        with open(os.path.join(OUT, f"pack_{f // 60:03d}.txt"), "w") as fh:
            for i in range(f, min(f + 60, len(items))):
                fh.write(f"### R{i:04d}\n{items[i][1]}\n\n")
    print(f"{len(items)} bills -> {-(-len(items) // 60)} files of 60; no introduced summary: {dict(missing)}")


def load():
    import glob
    ids = json.load(open(os.path.join(OUT, "ids.json"))); out = {}; bad = 0
    lf = os.path.join(OUT, "leak_ids.json")                       # summaries that name the bill that absorbed this one
    leak = set(json.load(open(lf))) if os.path.exists(lf) else set()
    for f in glob.glob(os.path.join(OUT, "answers_*.jsonl")):
        for line in open(f):
            line = line.strip()
            if line.startswith("{"):
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    bad += 1; continue                             # counted below
                if d.get("id") in ids and d["id"] not in leak:
                    out[tuple(ids[d["id"]])] = d
    if bad:
        print(f"rubric: {bad} unreadable answer lines skipped")
    return out


if __name__ == "__main__":
    build() if (sys.argv[1] if len(sys.argv) > 1 else "build") == "build" else print(len(load()))
