"""Reader for California's pubinfo export (Legislative Counsel) — schema from the source, not from us.

The column order of every table is taken from the source's own load scripts (`<table>.sql` inside
pubinfo_load.zip: `LOAD DATA … (COL1, COL2, …)`). Rows are tab-delimited `.dat` files, fields optionally enclosed in
backticks; long text lives in `.lob` side files that a field names (never needed for the bill contract).

Fail closed (Standard #4): a row whose field count differs from the declared column list is COUNTED per table and
skipped; a table the export does not carry raises — a partial universe is never published.
"""
from __future__ import annotations

import collections
import io
import re
import zipfile
from typing import Dict, Iterator, List, Optional, Tuple

_COLS_RE = re.compile(r"\(\s*(.*?)\s*\)\s*(?:SET|;|$)", re.S)


def columns_from_load_sql(sql: str) -> List[str]:
    """`LOAD DATA … INTO TABLE capublic.x … ( A ,B ,@var1 ,C )` -> ['A', 'B', '@var1', 'C']."""
    body = sql[sql.index("(", sql.upper().index("LINES TERMINATED")):]
    m = _COLS_RE.search(body)
    if not m:
        raise ValueError("load script has no column list")
    return [c.strip() for c in m.group(1).replace("\n", " ").split(",") if c.strip()]


def load_schema(load_zip: bytes) -> Dict[str, List[str]]:
    z = zipfile.ZipFile(io.BytesIO(load_zip))
    out = {}
    for n in z.namelist():
        if n.endswith("_tbl.sql"):
            out[n[:-4].upper()] = columns_from_load_sql(z.read(n).decode("utf-8", "replace"))
    if not out:
        raise ValueError("pubinfo_load.zip carries no table load scripts")
    return out


def _field(v: str) -> str:
    v = v.rstrip("\r")
    if len(v) >= 2 and v[0] == "`" and v[-1] == "`":
        v = v[1:-1]
    return "" if v == "NULL" else v


class Export:
    """One pubinfo zip (full session or a day's increment). `rows(table)` yields dicts keyed by column name."""

    def __init__(self, blob_or_path, schema: Dict[str, List[str]]):
        self.z = zipfile.ZipFile(blob_or_path if not isinstance(blob_or_path, (bytes, bytearray)) else io.BytesIO(blob_or_path))
        self.schema = schema
        self.names = {n.split("/")[-1].upper(): n for n in self.z.namelist()}
        self.bad_rows: Dict[str, int] = collections.Counter()

    def has(self, table: str) -> bool:
        return f"{table}.DAT" in self.names

    def rows(self, table: str, required: bool = True) -> Iterator[Dict[str, str]]:
        key = f"{table}.DAT"
        if key not in self.names:
            if required:
                raise KeyError(f"pubinfo export has no {table}.dat — refusing to build (fail closed)")
            return
        cols = self.schema[table]
        with self.z.open(self.names[key]) as f:
            for raw in io.TextIOWrapper(f, encoding="utf-8", errors="replace", newline="\n"):
                parts = raw.rstrip("\n").split("\t")
                if len(parts) != len(cols):
                    self.bad_rows[table] += 1          # counted, never guessed into place
                    continue
                yield {c: _field(v) for c, v in zip(cols, parts)}


def bill_id_parts(bill_id: str) -> Optional[Tuple[str, str, str]]:
    """'20250AB123' -> ('20252026'? no — the id carries session_year+session_num+type+number): returns
    (session prefix, measure type, number) or None. Format read off the export: 4-digit year, 4-digit end year,
    session number, type letters, number (e.g. '202520260AB123')."""
    m = re.match(r"^(\d{8})(\d)([A-Z]+)(\d+)$", bill_id or "")
    return (m.group(1) + m.group(2), m.group(3), str(int(m.group(4)))) if m else None
