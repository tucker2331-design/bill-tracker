#!/usr/bin/env python3
"""Stakeholder lineups -- do published positions and public testimony add to the model? (owner cleared 2026-09-29)

Two sources, each tested with accept.stacked_year_ahead (fit on earlier years' out-of-sample predictions, score the
next year; pooled over 2022 / 2024 / 2025; accept at z >= 3):

  VALCV      the Virginia League of Conservation Voters' own Support / Oppose on its scorecard bills
             (tools/historical_cache/va_positions.py). Inputs: position x voter's party (it is a partisan lineup
             signal, so the same position means opposite things for the two caucuses).
  HODSpeak   written testimony on the bill submitted to a House committee meeting on or before the vote
             (tools/historical_cache/hodspeak_comments.py; counts only). Inputs: has, log comments, share reading as
             support / opposition, organizations commenting -- and each x "voter is the patron's party".

Why neither is tested on bill FATE: testimony only exists once a bill is on a meeting agenda, and a scorecard picks
its bills after the session -- both are downstream of the fate they would predict (leakage by construction).
"""
from __future__ import annotations
import sys, os, json, math, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import accept as AC
import first_vote as FV

HC = os.path.join(HERE, "..", "historical_cache")


def valcv_signal():
    P = json.load(open(os.path.join(HC, "va_positions", "valcv.json")))["positions"]
    def sig(r):
        s, b = r["bill"]
        pos = {"Support": 1.0, "Oppose": -1.0}.get(P.get(s, {}).get(b), 0.0)
        d = r["party"] == FV.PARTIES[0]
        return {"lcv_x_dem": pos * d, "lcv_x_rep": pos * (not d), "lcv_has": float(pos != 0)}
    return sig


def hodspeak_signal():
    rc = FV.assemble()["rc"]
    cards = collections.defaultdict(list)                  # (session, "HB 41") -> [(date, counts)]
    for f in os.listdir(os.path.join(HC, "va_hodspeak")):
        if not f.endswith(".json"):
            continue
        y = f[:4]
        for m in json.load(open(os.path.join(HC, "va_hodspeak", f)))["meetings"].values():
            for bill, c in m["bills"].items():
                k = (y, bill[:2] + " " + bill[2:])
                cards[k].append((m["date"], c))
    def sig(r):
        day = rc[r["bill"]][0][0]
        cs = [c for d, c in cards.get(r["bill"], []) if d <= day]
        n = sum(c["comments"] for c in cs)
        if not cs:
            return {k: 0.0 for k in ("h_has", "h_n", "h_sup", "h_opp", "h_orgs", "h_n_same", "h_sup_same",
                                     "h_opp_same")}
        sup = sum(c["support"] for c in cs) / n if n else 0.0
        opp = sum(c["oppose"] for c in cs) / n if n else 0.0
        orgs = math.log1p(len({o for c in cs for o in c["orgs"]}))
        same = float(r["same"])
        return {"h_has": 1.0, "h_n": math.log1p(n), "h_sup": sup, "h_opp": opp, "h_orgs": orgs,
                "h_n_same": math.log1p(n) * same, "h_sup_same": sup * same, "h_opp_same": opp * same}
    return sig


if __name__ == "__main__":
    which = sys.argv[1:] or ["valcv", "hodspeak"]
    if "valcv" in which:
        AC.stacked_year_ahead(valcv_signal(), "VALCV position x voter party (all ballots)")
        AC.stacked_year_ahead(valcv_signal(), "VALCV position x voter party (ballots on scored bills only)",
                              only_covered=True)
    if "hodspeak" in which:
        AC.stacked_year_ahead(hodspeak_signal(), "HODSpeak written testimony (all ballots)")
        AC.stacked_year_ahead(hodspeak_signal(), "HODSpeak written testimony (ballots with testimony only)",
                              only_covered=True)
