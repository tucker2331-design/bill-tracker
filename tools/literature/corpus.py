#!/usr/bin/env python3
"""The reading list for what a lobbyist actually needs, fetched and cached as text.

WHY THIS EXISTS
---------------
Owner, 2026-09-10: *"think big picture collect literature titles essays interviews etc from lobbyists and
those that might be relevent in our hunt for relevent historical info and signals for displaying to our
lobbyists."*

Every indicator in this project so far was derived bottom-up from whatever happened to be in the data.
That is how we ended up measuring floor votes for weeks while the deciding room (the subcommittee) sat
unopened in a cached file. A reading list is the corrective: it says what the field already knows works,
what has already been tried and failed, and which signals practitioners actually act on — BEFORE we spend
another week deriving something that was settled in 2009.

SELECTION RULE
--------------
Deliberately mixed in medium AND in whose interest the author serves, because each kind lies differently:

  peer-reviewed      has denominators and controls, but studies Congress far more often than statehouses
  practitioner guide knows what actually happens in a hearing room, and is selling something
  journalism         finds the specific scandal a dataset averages away; not systematic
  government/CRS     definitive on procedure, silent on effectiveness
  trade/vendor       describes what customers already pay for — i.e. the competitive baseline

A claim that survives in ALL of them is worth building on. A claim that appears in only one is a lead.

CACHING
-------
Each source is fetched once to `sources/<slug>.txt` with a manifest recording url, fetched date, word
count and sha256. Re-running costs nothing. Word count is recorded because the owner asked for depth, and
because "I read it" is not checkable while "it is 14,000 words and here is the file" is.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "sources")
MANIFEST = os.path.join(HERE, "manifest.json")
# A normal browser UA. Several publishers 403 anything that self-identifies as a script, including a
# 2017 local-news article that is otherwise freely readable. This fetches each public page ONCE, caches
# it, and sleeps between requests — human-scale reading, not scraping. Where a publisher blocks this too
# (congress.gov, OpenSecrets, Annual Reviews), the source is recorded as UNREAD rather than worked around;
# see manifest errors and docs/testing/literature.md.
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
      "Accept-Language": "en-US,en;q=0.9"}
DELAY = 1.5

# medium / perspective / why it is on the list. `kind` drives how it is read, not just how it is labelled.
SOURCES = [
    {"slug": "eidelman-2018-how-predictable-is-your-state", "kind": "peer-reviewed",
     "title": "How Predictable is Your State? Leveraging Lexical and Contextual Information for "
              "Predicting Legislative Floor Action at the State Level",
     "who": "Eidelman, Kornilova, Argyle (FiscalNote) — COLING 2018",
     "url": "https://aclanthology.org/C18-1013.pdf",
     "why": "THE closest prior art: 1.3M bills, 50 states + DC, ~10 sessions each. Predicts FLOOR ACTION "
            "at 85.9% acc / 0.85 AUROC. Reports committee information as the MOST predictive feature, "
            "sponsor second, bill text only a modest gain — which is our structural-over-text thesis, "
            "measured at national scale by someone else."},
    {"slug": "nay-2017-predicting-law-making", "kind": "peer-reviewed",
     "title": "Predicting and understanding law-making with word vectors and an ensemble model",
     "who": "John J. Nay — PLOS ONE, 2017",
     "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC5425031/",
     "why": "~70,000 bills, 103rd-113th Congress, AUC up to 0.96. Top features: sponsor's party in the "
            "MAJORITY, then text, then COSPONSOR COUNT, then sponsor experience — independent "
            "confirmation of our minority-penalty and co-patron findings on a different corpus."},
    {"slug": "yano-2012-bill-survival-committee", "kind": "peer-reviewed",
     "title": "Textual Predictors of Bill Survival in Congressional Committees",
     "who": "Yano, Smith, Wilkerson — NAACL 2012",
     "url": "https://aclanthology.org/N12-1033.pdf",
     "why": "Predicts the COMMITTEE stage specifically — 'one of the most precarious and least understood "
            "stages in a bill's life'. The direct precedent for [[testing/kill_points]]."},
    {"slug": "nay-2016-arxiv-preprint", "kind": "peer-reviewed",
     "title": "Predicting and Understanding Law-Making with Word Vectors and an Ensemble Model (preprint)",
     "who": "John J. Nay — arXiv 1607.02109",
     "url": "https://arxiv.org/abs/1607.02109",
     "why": "Preprint of the PLOS paper; carries method detail the journal version compresses."},
    {"slug": "shor-kistner-comparing-leviathans", "kind": "peer-reviewed",
     "title": "Comparing Leviathans: Agenda Influence in State Legislatures, 2011 to 2023",
     "who": "Shor & Kistner — USC Price School",
     "url": "https://priceschool.usc.edu/wp-content/uploads/2024/10/Shor-and-Kistner.pdf",
     "why": "STATE-level negative agenda control across a decade — how majorities keep bills off the "
            "floor. The theory behind the kill-point map we measured in Virginia."},
    {"slug": "kwak-2026-gatekeepers-subcommittee", "kind": "peer-reviewed",
     "title": "Who Controls the Legislative Process? Party Cartels, Committee Gatekeepers, and "
              "Subcommittee Activity",
     "who": "Kwak — Legislative Studies Quarterly, 2026",
     "url": "https://onlinelibrary.wiley.com/doi/full/10.1111/lsq.70072",
     "why": "Explicitly about SUBCOMMITTEE activity as the gatekeeping venue — the one room our own data "
            "says decides Virginia outcomes, treated theoretically."},
    {"slug": "drutman-dissertation-business-of-lobbying", "kind": "peer-reviewed",
     "title": "The Business of America is Lobbying: The Expansion of Corporate Political Activity and "
              "the Future of American Pluralism (dissertation)",
     "who": "Lee Drutman — UC Berkeley PhD dissertation",
     "url": "https://escholarship.org/content/qt1mh761v2/qt1mh761v2_noSplash_c46add0559320655f6691c997d1b10ec.pdf",
     "why": "BOOK-LENGTH and openly available — the full argument behind the 2015 OUP book, with the "
            "data appendices the trade edition drops. Explains who our buyers are and what they must "
            "justify internally."},
    {"slug": "harvard-three-essays-on-lobbying", "kind": "peer-reviewed",
     "title": "Three Essays on Lobbying (PhD dissertation)",
     "who": "Harvard University — DASH open repository",
     "url": "https://dash.harvard.edu/server/api/core/bitstreams/9f8d0eb3-f563-449b-a6f2-c986eb8933bf/content",
     "why": "Dissertation-length empirical treatment of special-interest lobbying; long enough to carry "
            "full method and null results, which journal versions compress out."},
    {"slug": "butler-miller-does-lobbying-affect-bill-advancement", "kind": "peer-reviewed",
     "title": "Does Lobbying Affect Bill Advancement? Evidence from Three State Legislatures",
     "who": "Daniel M. Butler, David R. Miller — Political Research Quarterly, 2022",
     "url": "https://www.davidryanmiller.com/files/LobbyingImpact.pdf",
     "why": "STATE-level and directly on our outcome variable — whether lobbying moves BILL ADVANCEMENT, "
            "not final passage. Nearly all the rest of the literature is federal."},
    {"slug": "annual-review-how-lobbying-matters", "kind": "peer-reviewed",
     "title": "How Lobbying Matters",
     "who": "Annual Review of Political Science",
     "url": "https://www.annualreviews.org/content/journals/10.1146/annurev-polisci-033123-124920",
     "why": "A recent survey of the whole field — the fastest way to find which of our findings are "
            "already settled, already contested, or genuinely unexamined."},
    {"slug": "crs-lobbying-disclosure-act-at-20", "kind": "government",
     "title": "The Lobbying Disclosure Act at 20: Analysis and Issues for Congress (R44292)",
     "who": "Congressional Research Service",
     "url": "https://www.congress.gov/crs-product/R44292",
     "why": "Definitive on what lobbying activity is legally required to be disclosed — i.e. which "
            "signals about our own users' behaviour are public record and which are not."},
    {"slug": "va-general-assembly-glossary", "kind": "government",
     "title": "Glossary & Legislative Terms — Virginia General Assembly",
     "who": "Virginia General Assembly (official)",
     "url": "https://vga.virginia.gov/learn/glossary-legislative-terms/",
     "why": "The publisher's OWN definitions of the action vocabulary our classifiers parse "
            "('passed by indefinitely', 'stricken from docket', 'continued to'). Authoritative for "
            "Standard #3 structural mapping."},
    {"slug": "rvahub-2017-unrecorded-subcommittee-votes", "kind": "journalism",
     "title": "Most House bills died on unrecorded votes in 2017 General Assembly session",
     "who": "RVAHub / VCU Capital News Service, 2017",
     "url": "https://rvahub.com/2017/03/06/interactive-house-bills-died-unrecorded-votes-2017-general-"
            "assembly-session/",
     "why": "CRITICAL CAVEAT ON OUR OWN FINDING: reports that of 571 failed 2017 House bills, more than "
            "TWO-THIRDS were killed on unrecorded voice votes in subcommittee. Those kills cannot appear "
            "in Vote.csv, so our recorded subcommittee roll calls are a SUBSET and the subcommittee is an "
            "even bigger kill point than we measured."},
    {"slug": "virginia-mercury-alive-and-dead-2026", "kind": "journalism",
     "title": "What's alive and what's dead at the Virginia General Assembly's 2026 midway point",
     "who": "Virginia Mercury, Feb 2026",
     "url": "https://virginiamercury.com/2026/02/18/whats-alive-and-whats-dead-at-the-virginia-general-"
            "assemblys-2026-midway-point/",
     "why": "What a working Virginia reporter thinks is worth tracking at crossover — a free read on "
            "which bills and signals an informed audience considers newsworthy."},
    {"slug": "plural-how-to-lobby-state-level", "kind": "practitioner",
     "title": "How to Lobby at the State Level",
     "who": "Plural Policy (vendor)",
     "url": "https://pluralpolicy.com/blog/how-to-lobby-at-the-state-level/",
     "why": "A direct competitor's own description of the workflow — the baseline our product must beat."},
    {"slug": "quorum-state-lobbying-new-legislatures", "kind": "practitioner",
     "title": "State Lobbying Strategy: Tips for New Legislatures",
     "who": "Quorum (vendor)",
     "url": "https://www.quorum.us/blog/prepping-for-new-faces-state-legislatures/",
     "why": "Competitor framing of the new-session problem — freshman legislators, committee reshuffles — "
            "which is exactly where our seniority and persuadability data would apply."},
    {"slug": "bgov-lobbying-state-vs-federal", "kind": "practitioner",
     "title": "Lobbying State Governments vs. the Federal Government",
     "who": "Bloomberg Government",
     "url": "https://about.bgov.com/insights/public-affairs-strategies/lobbying-state-governments-vs-the-"
            "federal-government/",
     "why": "Why state work differs from federal — speed, thin staff, short sessions. Bears on which of "
            "the Congress-based literature above actually transfers to Virginia."},
    {"slug": "opensecrets-lobbying-timeline", "kind": "reference",
     "title": "Lobbying Timeline",
     "who": "OpenSecrets",
     "url": "https://www.opensecrets.org/resources/learn/lobbying_timeline",
     "why": "Historical arc of the profession and its disclosure regime — context for what data has "
            "existed when, which bounds any historical backtest."},
    {"slug": "senate-oral-history", "kind": "interview",
     "title": "Oral History Project — U.S. Senate Historical Office",
     "who": "U.S. Senate Historical Office",
     "url": "https://www.senate.gov/history/oralhistory.htm",
     "why": "First-person accounts from staff and members of how decisions were ACTUALLY made — the "
            "mechanism behind the statistics, in the words of people in the room."},
    {"slug": "house-oral-history", "kind": "interview",
     "title": "Oral History Program — U.S. House of Representatives",
     "who": "Office of the Historian, U.S. House",
     "url": "https://history.house.gov/About/Oral-History/Program-Overview/",
     "why": "Companion to the Senate program; explicitly documents 'legislative processes and procedures' "
            "and how the institution's norms shifted over time."},
]

BOOKS = [
    {"title": "Lobbying and Policy Change: Who Wins, Who Loses, and Why",
     "who": "Baumgartner, Berry, Hojnacki, Kimball, Leech — Univ. of Chicago Press, 2009",
     "url": "https://press.uchicago.edu/ucp/books/book/chicago/L/bo6683614.html",
     "why": "The definitive empirical study of lobbying outcomes: 98 randomly selected issues tracked "
            "over four years. Headline findings — ~60% of campaigns produced NO policy change, and "
            "RESOURCES EXPLAIN UNDER 5% of the variance between winning and losing. If true in Virginia "
            "it reframes the product: the edge is not money, it is knowing where the veto points are."},
    {"title": "The Business of America is Lobbying",
     "who": "Lee Drutman — Oxford University Press, 2015",
     "url": "https://archive.org/details/businessofameric0000drut",
     "why": "How corporate lobbying became proactive and particularistic rather than defensive. Explains "
            "WHO our users are and what they are being asked to justify internally."},
    {"title": "Guide to State Legislative Lobbying (3rd ed.)",
     "who": "Robert L. Guyer — Engineering THE LAW, Inc.",
     "url": "https://www.amazon.com/Guide-State-Legislative-Lobbying-Third/dp/0967724228",
     "why": "A practitioner manual specifically for STATE work, where nearly all the academic literature "
            "is federal. Closest thing to a written account of the job our users actually do."},
]


def _slugpath(slug):
    return os.path.join(SRC, slug + ".txt")


def _manifest():
    if os.path.exists(MANIFEST):
        with open(MANIFEST, encoding="utf-8") as fh:
            return json.load(fh)
    return {"sources": {}}


def _save(man):
    with open(MANIFEST, "w", encoding="utf-8") as fh:
        json.dump(man, fh, indent=1, sort_keys=True)
        fh.write("\n")


def _html_to_text(raw):
    t = raw.decode("utf-8", "replace")
    t = re.sub(r"(?is)<(script|style|nav|footer|header)[^>]*>.*?</\1>", " ", t)
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    t = (t.replace("&nbsp;", " ").replace("&amp;", "&").replace("&#8217;", "'")
         .replace("&quot;", '"').replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]{2,}", " ", t)).strip()


def _pdf_to_text(path):
    import pypdf
    r = pypdf.PdfReader(path)
    return "\n".join((p.extract_text() or "") for p in r.pages)


def fetch(only=None):
    os.makedirs(SRC, exist_ok=True)
    man = _manifest()
    got = skipped = failed = 0
    for s in SOURCES:
        if only and only not in s["slug"]:
            continue
        if os.path.exists(_slugpath(s["slug"])) and man["sources"].get(s["slug"]):
            skipped += 1
            continue
        try:
            req = urllib.request.Request(s["url"], headers=UA)
            with urllib.request.urlopen(req, timeout=90) as r:
                raw = r.read()
                ctype = r.headers.get("Content-Type", "")
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            # COUNTED, never silent: a paywalled or 403 source is a known gap in the reading, and a
            # reading list that quietly omits what it could not read is worse than one that says so.
            print(f"  FAIL {s['slug']}: {exc}")
            man["sources"][s["slug"]] = {"url": s["url"], "error": str(exc),
                                         "checked": time.strftime("%Y-%m-%d")}
            failed += 1
            time.sleep(DELAY)
            continue
        if "pdf" in ctype.lower() or s["url"].lower().endswith(".pdf"):
            tmp = _slugpath(s["slug"]) + ".pdf"
            with open(tmp, "wb") as fh:
                fh.write(raw)
            try:
                text = _pdf_to_text(tmp)
            except Exception as exc:
                print(f"  FAIL {s['slug']}: pdf extract — {exc}")
                man["sources"][s["slug"]] = {"url": s["url"], "error": f"pdf: {exc}",
                                             "checked": time.strftime("%Y-%m-%d")}
                failed += 1
                continue
        else:
            text = _html_to_text(raw)
        words = len(text.split())
        with open(_slugpath(s["slug"]), "w", encoding="utf-8") as fh:
            fh.write(text)
        man["sources"][s["slug"]] = {
            "url": s["url"], "title": s["title"], "who": s["who"], "kind": s["kind"],
            "words": words, "sha256": hashlib.sha256(text.encode()).hexdigest()[:16],
            "fetched": time.strftime("%Y-%m-%d")}
        print(f"  ok   {s['slug']}: {words:,} words")
        got += 1
        time.sleep(DELAY)
    _save(man)
    print(f"\nfetched {got}, cached {skipped}, failed {failed}")
    return 0


def status():
    man = _manifest()
    rows = []
    for s in SOURCES:
        rec = man["sources"].get(s["slug"], {})
        rows.append((s["kind"], s["slug"], rec.get("words"), rec.get("error")))
    print(f"{'kind':<15}{'source':<48}{'words':>9}")
    tot = 0
    by = {}
    for kind, slug, w, err in sorted(rows):
        tot += w or 0
        by[kind] = by.get(kind, 0) + (1 if w else 0)
        print(f"{kind:<15}{slug[:46]:<48}{(f'{w:,}' if w else 'FAILED: ' + (err or '?')[:22]):>9}")
    print(f"\ntotal fetched words: {tot:,}")
    print(f"sources >=10,000 words: {sum(1 for _k, _s, w, _e in rows if (w or 0) >= 10000)}")
    print(f"by kind: {by}")
    print(f"plus {len(BOOKS)} book-length works (not fetchable in full; see docs/testing/literature.md)")
    return 0


if __name__ == "__main__":
    sys.exit(status() if "--status" in sys.argv else fetch())
