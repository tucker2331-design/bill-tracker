// "Our position" on a bill — the team's own entry, shared through the Worker (F2). Grey by default: the four
// stances are small-caps TEXT, the current one in full ink, never a coloured chip (doctrine rule 5 / P20a —
// an org-asserted value must not look like a sourced one). Saving is confirmed by the server before the
// screen changes, so the page never shows a position the team does not actually have.
import { useState } from "react";
import { useIdentity } from "../state/auth";
import { STANCES, STANCE_LABEL, savePosition, usePositions, type Stance } from "../state/positions";

const shortDate = (iso: string) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleDateString(undefined, { day: "numeric", month: "short" });
};

export function PositionControl({ bill, sessionCode }: { bill: string; sessionCode: string }) {
  const identity = useIdentity();
  const { status, byBill } = usePositions(sessionCode);
  const [saving, setSaving] = useState<Stance | "clear" | null>(null);
  const [err, setErr] = useState("");

  if (status === "signed_out") return <span className="muted">Sign in to see and set your team's position.</span>;
  if (status === "not_member") return <span className="muted">Your account isn't on this team's list.</span>;
  if (status === "not_configured") return <span className="muted">Team positions aren't set up yet.</span>;
  if (status === "error") return <span className="muted">Couldn't load your team's positions.</span>;
  if (status === "loading") return <span className="muted">Loading…</span>;

  const cur = byBill.get(bill);
  const choose = async (s: Stance | null) => {
    setErr(""); setSaving(s ?? "clear");
    try { await savePosition(sessionCode, bill, s, identity?.email ?? ""); }
    catch (e) { setErr(e instanceof Error ? e.message : "Couldn't save. Nothing was changed."); }
    finally { setSaving(null); }
  };

  return (
    <span className="pos">
      <span className="pos-row" role="radiogroup" aria-label="Our position">
        {STANCES.map((s) => (
          <button key={s} type="button" role="radio" aria-checked={cur?.stance === s}
            className={`pos-opt${cur?.stance === s ? " on" : ""}`} disabled={saving !== null}
            onClick={() => choose(cur?.stance === s ? null : s)}
            title={cur?.stance === s ? "Click again to clear" : undefined}>
            {saving === s ? "Saving…" : STANCE_LABEL[s]}
          </button>
        ))}
      </span>
      <span className="muted pos-meta">
        {cur ? `set by ${cur.updatedBy}${shortDate(cur.updatedAt) ? ` · ${shortDate(cur.updatedAt)}` : ""} · your team's entry, not from LIS`
             : "no position set · your team's entry, not from LIS"}
      </span>
      {err && <span className="pos-err">{err}</span>}
    </span>
  );
}

/** The War Room list's read-only column: the stance as small-caps text, or nothing. */
export function PositionTag({ bill, sessionCode }: { bill: string; sessionCode: string }) {
  const { status, byBill } = usePositions(sessionCode);
  const p = status === "ready" ? byBill.get(bill) : undefined;
  return <span className="wr-pos">{p ? STANCE_LABEL[p.stance] : ""}</span>;
}
