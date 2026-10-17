#!/usr/bin/env python3
"""What is SAID about a bill in committee -- per-bill segments from Internet Archive closed captions.

Source: tools/historical_cache/ia_transcripts.py (caption text only). The captions are broadcast closed captions: upper
case, '>>' at each change of speaker, bills read aloud as 'HOUSE BILL 1234' / 'SENATE BILL 1265'.

SEGMENTING: every caption line belongs to the bill most recently named, until a different bill is named. A bill named
again later in the same meeting (e.g. re-taken after a substitute) adds a second stretch to the same segment.
Per (meeting, bill):  seconds, words, turns (speaker changes), public (count of 'MY NAME IS'), oppose / support
(statements like 'IN OPPOSITION', 'SPEAK IN SUPPORT'), questions ('?'), members (distinct 'DELEGATE X' / 'SENATOR X'
named), motion words heard (report / table / pass by indefinitely / continue / strike).
Session meetings only (January-March); interim meetings are skipped and counted.

Run: python3 tools/calibration/transcripts.py          -> tools/historical_cache/va_transcripts/segments.json
"""
from __future__ import annotations
import os, re, json, collections

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "historical_cache", "va_transcripts")
# text can sit on the timestamp line itself ("00:00:06.000 --> 00:00:08.000 >> IF YOU WOULD...") or on the lines below
CUE = re.compile(r"(\d\d):(\d\d):(\d\d)\.\d+ --> \S+([^\n]*)\n((?:(?!\d\d:\d\d:\d\d\.\d+ -->)[^\n]*\n?)*)")
# 2019-era captions are upper case with '>>' speaker marks; 2023+ captions are mixed case with no '>>' and can split
# "House Bill" / "1104" across two caption lines -- so text is upper-cased and each line is read with the previous one
BILL = re.compile(r"\b(?:(HOUSE|SENATE) BILL(?: NUMBER)?|(H|S)\.? ?B\.?) ?(\d{1,4})\b")
MEMBER = re.compile(r"\b(?:DELEGATE|SENATOR|DEL\.|SEN\.) ([A-Z][A-Z'\-]{2,})")
MOTIONS = {"report": r"MOVE(?:D)? (?:TO |THAT WE )?REPORT|MOTION TO REPORT",
           "table": r"LAY (?:IT )?ON THE TABLE|MOTION TO TABLE|TABLE THE BILL",
           "pbi": r"PASS(?:ED)? BY INDEFINITELY", "continue": r"CONTINUE (?:TO|THE BILL|IT) ", "strike": r"STRIKE"}


def cues(text):
    out = []
    for h, m, s, inline, body in CUE.findall(text):
        t = re.sub(r"\s+", " ", f"{inline} {body}").strip()
        if t:
            out.append((int(h) * 3600 + int(m) * 60 + int(s), t))
    return out


def segment(text):
    segs = collections.defaultdict(lambda: {"seconds": 0, "words": 0, "turns": 0, "public": 0, "oppose": 0,
                                            "support": 0, "questions": 0, "members": set(),
                                            **{f"m_{k}": 0 for k in MOTIONS}})
    cur = None; prev_t = None; prev_line = ""
    has_marks = ">>" in text
    for t, line in cues(text):
        line = line.upper()
        joined = (prev_line[-20:] + " " + line) if prev_line else line
        named = BILL.findall(joined)
        prev_line = line
        if named:
            long_, short, num = named[-1]
            ch = long_ or ("HOUSE" if short == "H" else "SENATE")
            cur = f"{'HB' if ch == 'HOUSE' else 'SB'} {int(num)}"
        if cur is None:
            prev_t = t; continue
        s = segs[cur]
        if prev_t is not None and 0 <= t - prev_t <= 120:
            s["seconds"] += t - prev_t
        prev_t = t
        s["words"] += len(line.split())
        # speaker turns: '>>' marks where the captions have them, otherwise a member recognized by name
        s["turns"] += line.count(">>") if has_marks else len(MEMBER.findall(line))
        s["public"] += len(re.findall(r"MY NAME IS", line))
        s["oppose"] += len(re.findall(r"IN OPPOSITION|OPPOSE[DS]? (?:TO )?(?:THE|THIS) BILL|SPEAK(?:ING)? AGAINST", line))
        s["support"] += len(re.findall(r"IN SUPPORT|SUPPORT (?:OF )?(?:THE|THIS) BILL|SPEAK(?:ING)? FOR", line))
        s["questions"] += line.count("?")
        s["members"] |= set(MEMBER.findall(line))
        for k, pat in MOTIONS.items():
            s[f"m_{k}"] += len(re.findall(pat, line))
    return {b: {**v, "members": sorted(v["members"])} for b, v in segs.items()}


def main():
    index = json.load(open(os.path.join(SRC, "raw", "index.json")))
    out, skipped = {}, collections.Counter()
    for ident, meta in index.items():
        if meta.get("status") != "ok":
            skipped[meta.get("status", "?")] += 1; continue
        date = meta["date"]
        if not ("01" <= date[5:7] <= "03"):
            skipped["interim (not January-March)"] += 1; continue
        chamber = "H" if "-house-" in ident else "S" if "-senate-" in ident else "?"
        segs = segment(open(os.path.join(SRC, "raw", f"{ident}.vtt"), errors="replace").read())
        if not segs:
            skipped["no bill named in the captions"] += 1
        out[ident] = {"date": date, "session": date[:4], "chamber": chamber, "title": meta.get("title", ""), "bills": segs}
    json.dump(out, open(os.path.join(SRC, "segments.json"), "w"), indent=0, sort_keys=True)
    nb = sum(len(v["bills"]) for v in out.values())
    by = collections.Counter((v["session"], v["chamber"]) for v in out.values())
    print(f"session meetings {len(out)}, bill segments {nb}; by session/chamber {dict(sorted(by.items()))}; skipped {dict(skipped)}")


if __name__ == "__main__":
    main()
