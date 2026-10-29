#!/usr/bin/env python3
"""AI bill-reading PILOT -- prepared, NOT run (owner 2026-10-23: exhaust non-AI first; pilot on the ~$10 regular API
credit; leak plan in docs/testing/first_vote.md). INTERNAL ONLY until the owner's Standard #3 call.

Leak controls built in:
  1. Blind input: bill title + summary as introduced, with bill numbers, patron names, years, dates and committee
     names removed. Nothing about votes.
  2. Content, never outcome: the model rates how each party's legislators would likely view the bill.
  3. Memorization probe: a SEPARATE request asks whether it recognizes this exact bill and what happened to it; bills
     it "knows" are dropped from evaluation.
Sample: 100 bills from 2024 (the choose year): 50 from the model's hardest third, 50 random; subcommittee votes
preferred (low public exposure).
Modes:  build   writes the requests (.cache/llm_pilot_requests.jsonl) and prints a token / cost ESTIMATE -- no API
        submit  sends one Message Batch (needs `anthropic` installed and ANTHROPIC_API_KEY in the owner's terminal)
        collect reads the batch results into .cache/llm_pilot_results.json
Run: python3 llm_pilot.py build [model]
"""
from __future__ import annotations
import sys, os, re, json, random, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)

OUT = os.path.join(HERE, ".cache", "llm_pilot_requests.jsonl")
PRICE = {"claude-opus-5-5": (4.00, 20.00), "claude-haiku-5-5": (0.10, 0.50), "claude-sonnet-5-5": (2.00, 10.00)}  # $/MTok, skill table 2026-10-06
SYSTEM = ("You are a nonpartisan analyst of state legislation. You will read a short description of a bill. Judge only "
          "from the text how legislators of each major party would be likely to view it in a committee. Do not guess "
          "or recall what happened to any real bill.")
RATE_SCHEMA = {"type": "object", "additionalProperties": False,
               "required": ["democratic_support", "republican_support", "bipartisan_consensus", "costs_money"],
               "properties": {"democratic_support": {"type": "integer"}, "republican_support": {"type": "integer"},
                              "bipartisan_consensus": {"type": "integer"}, "costs_money": {"type": "boolean"}}}
PROBE_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["recognized", "outcome"],
                "properties": {"recognized": {"type": "boolean"},
                               "outcome": {"type": "string", "enum": ["passed", "failed", "unknown"]}}}


def blind(text):
    t = re.sub(r"\b(HB|SB|HJ|SJ|HR|SR)\s?\d+\b", "[bill]", text)
    t = re.sub(r"\b(19|20)\d{2}\b", "[year]", t)
    t = re.sub(r"\b(Delegate|Senator|Del\.|Sen\.)\s+[A-Z][\w'.-]+", r"\1 [name]", t)
    t = re.sub(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}\b", "[date]", t)
    return t


def sample():
    import numpy as np, gains as G, summary_memory as SM
    from corpus import load
    corpus = {(b["session"], b["bill"]): b for b in load()["bills"]}; summ = SM.summaries()
    te, p0, _p1 = G.load("choose")
    g = collections.defaultdict(list)
    for i, r in enumerate(te):
        g[r["bill"]].append(i)
    hard = {te[i]["bill"] for i in np.argsort(np.abs(p0 - .5))[:len(p0) // 3]}
    ok = [k for k in g if k in summ and any(te[i]["ven_sub"] for i in g[k])]
    rng = random.Random(2024)
    h = rng.sample(sorted(k for k in ok if k in hard), 50); rest = rng.sample(sorted(k for k in ok if k not in h), 50)
    return [(k, blind(corpus[k]["title"] + ". " + summ[k])) for k in h + rest]


def build(model):
    rows = sample(); n_in = n_out = 0; out = OUT.replace(".jsonl", f"_{model}.jsonl")
    with open(out, "w") as fh:
        for k, text in rows:
            for kind, schema, ask in (("rate", RATE_SCHEMA, "Rate 0-100 how likely most Democratic and most Republican "
                                       "committee members would be to support this bill, 0-100 how likely it is to get "
                                       "support from both parties, and whether it costs state money."),
                                      ("probe", PROBE_SCHEMA, "Do you recognize this exact bill from any source? If so, "
                                       "did it pass or fail? Say unknown if you do not know.")):
                req = {"custom_id": f"{kind}|{k[0]}|{k[1].replace(' ', '')}",
                       "params": {"model": model, "max_tokens": 1024, "system": SYSTEM,
                                  "output_config": {"effort": "low", "format": {"type": "json_schema", "schema": schema}},
                                  "messages": [{"role": "user", "content": f"{ask}\n\nBill:\n{text}"}]}}
                fh.write(json.dumps(req) + "\n")
                n_in += (len(SYSTEM) + len(ask) + len(text)) // 4 + 20; n_out += 300
    pi, po = PRICE[model]
    print(f"{len(rows)} bills -> {2 * len(rows)} requests written to {out}")
    print(f"ESTIMATE (not measured; ~4 chars/token, ~300 output tokens incl. thinking): input {n_in:,} tok, output {n_out:,} tok")
    print(f"  {model}: ${(n_in * pi + n_out * po) / 1e6:.2f} standard, ${(n_in * pi + n_out * po) / 2e6:.2f} with Batch (50%)")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "build"
    if mode == "build":
        for m in (sys.argv[2:] or ["claude-opus-5-5", "claude-haiku-5-5"]):
            build(m)
    else:
        raise SystemExit("submit / collect are deliberately not wired until the owner approves the install, the key "
                         "and the model (see the module docstring)")
