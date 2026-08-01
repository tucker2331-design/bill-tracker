#!/usr/bin/env python3
"""Round 3 — candidates from the ADHD divergence run (5 independent frames, 30 ideas, pruned).

Traps pruned before testing, with reasons:
  - "patron's dissent vs the committee median" (legislative + microstructure both proposed it) — this is
    `patron_agrees_with_cmte`, already DISQUALIFIED and then retested properly at -17.1%. Settled.
  - "roster overlap between patrons and the committee" (microstructure) — this is `cmte_member_copatrons`,
    already NOISE at -0.2%/+0.7%.
  - "sponsor coalition concentration" (microstructure) — a re-weighting of co-patron count (+0.3%) and
    majority share (already USABLE). Would mostly re-measure a known result.

TEXT PARSING NOTE: several of these read the catchline (`Bill_description`). Standard #3 forbids text
parsing on the LOBBYIST-FACING path but explicitly permits it for INTERNAL diagnostics. A backtest is
internal. If one of these survives and we want to ship it, it needs a structural source first — flagged
per stat below.
"""
import csv, io, re, sys, os, collections, datetime
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "historical_cache"))
from fetch import read_cached

def norm(b):
    m = re.match(r"^([A-Z]+)0*(\d+)$", (b or "").strip().upper())
    return f"{m.group(1)}{m.group(2)}" if m else (b or "").strip().upper()

def d8(s):
    m = re.match(r"^(\d{2})/(\d{2})/(\d{2})$", (s or "").strip())
    return f"20{m.group(3)}-{m.group(1)}-{m.group(2)}" if m else ""

def _days(a, b):
    try:
        return (datetime.date.fromisoformat(a) - datetime.date.fromisoformat(b)).days
    except Exception:
        return None

# The DLS drafting tag — the standardized clause DLS appends after the final semicolon of a catchline.
# The lobbyist frame's claim: "; penalty" drags a corrections fiscal note; "; report"/"; study" does
# nothing and passes on the block. Categories are matched on the LAST segment only.
def dls_tag(desc):
    segs = [s.strip().lower() for s in (desc or "").split(";") if s.strip()]
    if len(segs) < 2: return "none"
    t = segs[-1]
    for pat, lab in ((r"civil penalt", "civil penalty"), (r"penalt", "penalty"), (r"\breport\b", "report"),
                     (r"\bstudy\b|work group|advisory", "study"), (r"repeal", "repeal"),
                     (r"sunset|expiration", "sunset"), (r"definition", "definitions"),
                     (r"technical amend", "technical"), (r"effective date|emergency", "effective date"),
                     (r"\bfund\b|appropriat", "funding"), (r"exempt", "exemption"),
                     (r"\bfee\b|\btax\b", "fee/tax"), (r"\bpilot\b", "pilot")):
        if re.search(pat, t): return lab
    return "other"

LOCALITY = re.compile(r"\b(?:County|City|Town) of\b", re.I)
SECTION = re.compile(r"§+\s*[\d.:\-]+")

def build3(code, prior_desc=None, prior_outcome=None):
    B = {norm(r["Bill_id"]): r for r in csv.DictReader(io.StringIO(read_cached(code, "Bills.csv")))
         if (r.get("Bill_id") or "").strip()}
    spon = collections.defaultdict(list)
    for r in csv.DictReader(io.StringIO(read_cached(code, "Sponsors.csv"))):
        if (r.get("BILL_NUMBER") or "").strip(): spon[norm(r["BILL_NUMBER"])].append(r)
    # patron absence: share of X/A across all roll calls. Genuinely untested — loyalty and win rate
    # both CONDITION on being present; this measures whether they are in the room at all.
    resp = collections.defaultdict(collections.Counter)
    for r in csv.reader(io.StringIO(read_cached(code, "Vote.csv"))):
        if not r: continue
        for i in range(1, len(r) - 1, 2):
            resp[r[i].strip()][r[i + 1].strip()] += 1
    absence = {}
    for m, c in resp.items():
        tot = sum(c.values())
        if tot >= 20: absence[m] = (c["X"] + c["A"]) / tot

    intro_of = {b: d8(r.get("Introduction_date")) for b, r in B.items()}
    # same-day filing batch, per patron
    chief_of = {b: next((r["MEMBER_ID"].strip() for r in spon.get(b, [])
                         if (r.get("PATRON_TYPE") or "").startswith("1001")), "") for b in B}
    batch = collections.Counter((chief_of[b], intro_of[b]) for b in B if chief_of[b] and intro_of[b])
    # session-level deadline proxy: the date by which 95% of introductions have happened (a session
    # constant, so no per-bill leakage)
    ds = sorted(d for d in intro_of.values() if d)
    late_cut = ds[int(len(ds) * 0.90)] if ds else ""

    # prior-session recurrence ("zombie retread")
    def toks(s): return frozenset(w for w in re.sub(r"[^a-z ]", " ", (s or "").lower()).split() if len(w) > 3)
    prior_idx = collections.defaultdict(list)
    if prior_desc:
        for pb, pd in prior_desc.items():
            t = toks(pd)
            if t:
                for w in list(t)[:6]: prior_idx[w].append((pb, t))

    rows = []
    for bid, b in B.items():
        if bid[:2] not in ("HB", "SB"): continue
        desc = b.get("Bill_description") or ""
        h = bid[0] == "H"
        intro = intro_of[bid]
        tdates = sorted(d8(b.get(f"Full_text_date{i}")) for i in range(1, 7) if d8(b.get(f"Full_text_date{i}")))
        lead = _days(intro, tdates[0]) if tdates and intro else None
        ch = chief_of[bid]
        # recurrence
        rec = "no"
        if prior_idx:
            t = toks(desc); best = 0.0; bestb = None
            seen = set()
            for w in list(t)[:6]:
                for pb, pt in prior_idx.get(w, ()):
                    if pb in seen: continue
                    seen.add(pb)
                    j = len(t & pt) / len(t | pt) if (t | pt) else 0
                    if j > best: best, bestb = j, pb
            if best >= 0.6 and bestb:
                rec = "refiled-after-death" if prior_outcome and prior_outcome.get(bestb) == 0 else "refiled-after-success"
        y = {"survived": 0 if (b.get("Last_house_actid" if h else "Last_senate_actid") or "").strip().endswith("94") else 1,
             "passed": 1 if (b.get("Passed_house" if h else "Passed_senate") or "").strip().upper() == "Y" else 0}
        rows.append(({
            "dls_tag": dls_tag(desc),
            "catchline_segments": str(min(4, len([s for s in desc.split(";") if s.strip()]))),
            "names_locality": "Y" if LOCALITY.search(desc) else "N",
            "section_citations": ("0" if not SECTION.search(desc) else str(min(3, len(SECTION.findall(desc))))),
            "draft_lead_time": ("unknown" if lead is None else "same-week" if lead <= 7 else
                                "1-4wk" if lead <= 28 else "1-3mo" if lead <= 90 else "3mo+"),
            "same_day_batch": (lambda n: "1" if n <= 1 else "2-4" if n <= 4 else "5-9" if n <= 9 else "10+")(
                batch.get((ch, intro), 1)),
            "filed_late_in_window": "late" if intro and late_cut and intro >= late_cut else "early",
            "patron_absence": ("unknown" if ch not in absence else
                               "<2%" if absence[ch] < .02 else "2-6%" if absence[ch] < .06 else "6%+"),
            "prior_session_recurrence": rec,
        }, y, bid))
    return rows

def descs(code):
    B = {norm(r["Bill_id"]): (r.get("Bill_description") or "")
         for r in csv.DictReader(io.StringIO(read_cached(code, "Bills.csv"))) if (r.get("Bill_id") or "").strip()}
    return B

def outcomes(code):
    out = {}
    for r in csv.DictReader(io.StringIO(read_cached(code, "Bills.csv"))):
        b = norm(r.get("Bill_id", ""))
        if not b: continue
        h = b.startswith("H")
        out[b] = 0 if (r.get("Last_house_actid" if h else "Last_senate_actid") or "").strip().endswith("94") else 1
    return out
