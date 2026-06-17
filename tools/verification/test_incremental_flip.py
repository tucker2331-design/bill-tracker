"""Incremental-STM flip mechanics. The SHADOW validates events+telemetry on real cycles, but
it str-coerces both sides and so CANNOT see a type regression — that is locked in here.
See docs/knowledge/lis_api_safety.md / future_improvements Step 6."""
import os, sys
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import calendar_worker as cw


def _event(agenda_order):
    return {"Date": "2026-02-09", "Time": "10:00", "SortTime": "10:00", "Status": "Reported",
            "Committee": "H01 Courts", "Bill": "HB1", "Outcome": "Reported with amendments",
            "AgendaOrder": agenda_order, "Source": "DOCKET", "Origin": "api_schedule",
            "DiagnosticHint": "", "LegEventRoute": "meeting", "RefidClass": "", "ScheduleClass": "meeting"}


def main():
    fails = []

    # 1) THE critical one: key→reconstruct restores the int AgendaOrder, and the event is
    #    byte-identical to the original (incl. type) — for values where string sort would be WRONG.
    for ao in (-100, -1, 0, 1, 999):
        ev = _event(ao)
        recon = cw._reconstruct_stm_event(cw._stm_event_key(ev))
        if recon != ev:
            fails.append(f"1: round-trip changed the event for AgendaOrder={ao}: {recon}")
        if not isinstance(recon["AgendaOrder"], int):
            fails.append(f"1: AgendaOrder must reconstruct as int, got {type(recon['AgendaOrder'])} for {ao}")

    # 2) reconstruction works from a JSON-deserialized LIST (cache round-trips tuples as lists)
    ev = _event(7)
    key_as_list = list(cw._stm_event_key(ev))
    if cw._reconstruct_stm_event(key_as_list) != ev:
        fails.append("2: reconstruction from a list key must equal the original")

    # 3) all 14 fields are present after reconstruction
    recon = cw._reconstruct_stm_event(cw._stm_event_key(_event(1)))
    if set(recon.keys()) != set(cw._STM_EVENT_KEY_FIELDS):
        fails.append(f"3: reconstructed keys != the 14 fields: {set(recon.keys())}")

    # 4) a non-numeric AgendaOrder (e.g. an I1-filled "") is left as-is, matching the full run
    ev_blank = _event("")
    recon_blank = cw._reconstruct_stm_event(cw._stm_event_key(ev_blank))
    if recon_blank["AgendaOrder"] != "":
        fails.append(f"4: blank AgendaOrder must stay '' (got {recon_blank['AgendaOrder']!r})")

    # 5) AgendaOrder is asserted to be the ONLY non-string field — guard against a future addition
    #    silently breaking reconstruction (the shadow can't catch it).
    if cw._STM_EVENT_INT_FIELDS != ("AgendaOrder",):
        fails.append(f"5: _STM_EVENT_INT_FIELDS changed to {cw._STM_EVENT_INT_FIELDS} — update this test "
                     f"and confirm reconstruction handles the new non-string field")

    # 6) the shared-input signature is deterministic and sensitive to each input
    _dk = pd.DataFrame({"a": ["1", "2"]})
    base = dict(active_session="20261", df_docket=_dk, vote_id_set={"1", "2"},
                api_schedule_map={"k": {"x": 1}}, convene_times={"2026-02-09": {"H": {"Time": "10:00"}}})
    sig0 = cw._compute_stm_shared_sig(**base)
    if sig0 != cw._compute_stm_shared_sig(**base):
        fails.append("6: shared sig must be deterministic")
    for k, v in [("active_session", "20251"), ("vote_id_set", {"9"}),
                 ("api_schedule_map", {"k": {"x": 2}}),
                 ("convene_times", {"2026-02-09": {"H": {"Time": "11:00"}}})]:
        alt = dict(base); alt[k] = v
        if cw._compute_stm_shared_sig(**alt) == sig0:
            fails.append(f"6: shared sig must change when {k} changes")

    if fails:
        print("❌ FAILURES:")
        for x in fails:
            print("   -", x)
        sys.exit(1)
    print("✅ all incremental-flip tests passed (AgendaOrder int round-trip incl. ±100/999, "
          "list-key, 14-field, blank, single-int-field guard, shared-sig determinism+sensitivity)")


if __name__ == "__main__":
    main()
