"""The per-state contract (Standard #6 — scale to 50 states with zero per-state code paths in the pipeline).

A `StateConfig` holds EVERY fact about one legislature that the bill pipeline would otherwise hard-code: who
publishes the data, where, in what session-code format, which chambers exist and how a bill number names its
origin chamber, the stage list a bill moves through (and whether it has a crossover deadline), the clock the
legislature runs on, and the source's own status / floor vocabulary. The pipeline reads the config; it never
asks "is this Virginia?".

What is deliberately NOT here: anything derivable at runtime from the source (session code, committee list,
members — Standard #5). The config names WHERE to ask, never the answer.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Mapping, Pattern, Sequence


@dataclass(frozen=True)
class Stage:
    """One step of a bill's path. `marker` stages (a crossover deadline) are not places a bill sits."""
    id: str
    label: str
    marker: bool = False


@dataclass(frozen=True)
class StateConfig:
    code: str                         # USPS code, e.g. "VA"
    name: str                         # "Virginia"
    source_name: str                  # provenance stamped on every record, e.g. "LIS"
    timezone: str                     # IANA zone the legislature's calendar runs on ("today" is computed here)
    chambers: Mapping[str, str]       # bill/refid prefix letter -> chamber name, e.g. {"H": "House", "S": "Senate"}
    stages: Sequence[Stage]           # in order; includes any crossover marker
    session_years: int                # 1 = annual session (VA); 2 = two-year session (PA)
    bill_url_template: str            # public bill page; {session} {bill}
    urls: Mapping[str, str] = field(default_factory=dict)   # source endpoints by role (state-specific keys)
    # The source's own controlled status vocabulary for the keyword-FALLBACK outcome (never free prose).
    outcome_vocab: Mapping[str, Sequence[str]] = field(default_factory=dict)
    # The source's own floor-event phrases, per chamber name: {"House": {"passed": re, "defeated": re}}.
    floor_patterns: Mapping[str, Mapping[str, Pattern[str]]] = field(default_factory=dict)
    # Bill-number prefixes that pass BOTH chambers (a resolution may be single-chamber).
    two_chamber_bill_re: Pattern[str] = re.compile(r"(?!)")
    # The source's summary-type vocabulary -> lifecycle rank ("the latest summary"). Unknown types rank blank.
    summary_stage_rank: Mapping[str, int] = field(default_factory=dict)
    # Python module that provides this state's SOURCE machinery to the bill pipeline (session discovery, the
    # authorization gate, guarded fetches, committee resolution). See states/va_lis.py for the contract.
    adapter: str = ""

    @property
    def has_crossover(self) -> bool:
        return any(s.id == "crossover" for s in self.stages)

    def origin_chamber(self, bill: str) -> str:
        """The chamber a bill was introduced in, from its own number's prefix. Raises on an unknown prefix:
        a bill we cannot place is a contract break, never a silent default to the second chamber."""
        prefix = bill[:1].upper()
        if prefix not in self.chambers:
            raise ValueError(f"{self.code}: bill {bill!r} has no known chamber prefix {sorted(self.chambers)}")
        return self.chambers[prefix]

    def bill_url(self, session: str, bill: str) -> str:
        return self.bill_url_template.format(session=session, bill=bill)
