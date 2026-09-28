// The team's position on each bill — ORG-ASSERTED (P20a), stored in D1 behind the Worker (F2), shared by
// everyone on the team. The ladder is D1's settled enum (va_build_queue D1, owner 2026-07-27):
//   Involved (we wrote it / got it introduced) · Supporting · Watching · Opposing.
// It is never rendered as a sourced fact: it sits with the team's own entries, labelled as ours.
//
// States are kept distinct (pre-push audit #15) because each needs a different sentence on screen:
//   signed_out      -> "sign in to see and set your team's position"
//   loading         -> nothing yet
//   ready           -> the positions (an absent bill = no position set, a REAL answer once ready)
//   not_member      -> signed in, but not on this team's list
//   not_configured  -> the team list has not been set up on the server
//   error           -> the server could not be reached; NOT the same as "no positions"
import { useEffect, useSyncExternalStore } from "react";
import { APP_STATE } from "../config";
import { apiFetch, useIdentity } from "./auth";

export const STANCES = ["involved", "supporting", "watching", "opposing"] as const;
export type Stance = (typeof STANCES)[number];
export const STANCE_LABEL: Record<Stance, string> = {
  involved: "Involved", supporting: "Supporting", watching: "Watching", opposing: "Opposing",
};

export interface Position { stance: Stance; updatedAt: string; updatedBy: string; }
export type PositionsStatus = "signed_out" | "loading" | "ready" | "not_member" | "not_configured" | "error";
interface Snapshot { status: PositionsStatus; byBill: ReadonlyMap<string, Position>; key: string; }

const EMPTY = new Map<string, Position>();
let snap: Snapshot = { status: "signed_out", byBill: EMPTY, key: "" };
const listeners = new Set<() => void>();
const set = (s: Snapshot) => { snap = s; listeners.forEach((l) => l()); };
const subscribe = (l: () => void) => { listeners.add(l); return () => { listeners.delete(l); }; };

const isStance = (v: unknown): v is Stance => typeof v === "string" && (STANCES as readonly string[]).includes(v);

/** A 403 carries `reason` from the Worker's team gate; anything else unexpected is "error". */
async function statusFrom(res: Response): Promise<PositionsStatus> {
  if (res.status === 403) {
    const body = await res.json().catch(() => null);
    return body?.reason === "not_configured" ? "not_configured" : "not_member";
  }
  return "error";
}

async function load(key: string, session: string) {
  set({ status: "loading", byBill: EMPTY, key });
  try {
    const res = await apiFetch(`/api/positions?state=${encodeURIComponent(APP_STATE)}&session=${encodeURIComponent(session)}`);
    if (snap.key !== key) return;                                   // identity/session changed mid-flight
    if (!res.ok) { set({ status: await statusFrom(res), byBill: EMPTY, key }); return; }
    const body = await res.json();
    const m = new Map<string, Position>();
    let dropped = 0;
    for (const p of body?.positions ?? []) {
      if (isStance(p?.stance) && typeof p?.bill_number === "string") {
        m.set(p.bill_number, { stance: p.stance, updatedAt: p.updated_at ?? "", updatedBy: p.updated_by ?? "" });
      } else dropped++;
    }
    // The D1 CHECK constraint makes this impossible today; if it ever happens the enum drifted -- say so.
    if (dropped) console.warn(`Positions: ${dropped} row(s) with a stance outside ${STANCES.join("/")} were not shown.`);
    set({ status: "ready", byBill: m, key });
  } catch (e) {
    console.warn("Positions: load failed", e);
    if (snap.key === key) set({ status: "error", byBill: EMPTY, key });
  }
}

/** The team's positions for this session, reloaded when the signed-in person changes. */
export function usePositions(session: string) {
  const identity = useIdentity();
  const key = identity && session ? `${identity.email}|${session}` : "";
  useEffect(() => {
    if (!key) { if (snap.key !== "" || snap.status !== "signed_out") set({ status: "signed_out", byBill: EMPTY, key: "" }); return; }
    if (snap.key !== key) void load(key, session);
  }, [key, session]);
  return useSyncExternalStore(subscribe, () => snap);
}

/**
 * Set (or clear, with null) the team's position. Resolves only after the server confirms; the store is then
 * updated in place. Rejects with a sentence the UI can show -- nothing is changed locally on failure, so the
 * screen never shows a position the server does not have.
 */
export async function savePosition(session: string, bill: string, stance: Stance | null, by: string): Promise<void> {
  const res = stance
    ? await apiFetch("/api/positions", {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ state: APP_STATE, session_code: session, bill_number: bill, stance }),
      })
    : await apiFetch(`/api/positions?state=${encodeURIComponent(APP_STATE)}&session=${encodeURIComponent(session)}&bill_number=${encodeURIComponent(bill)}`,
        { method: "DELETE" });
  if (!res.ok) {
    const s = await statusFrom(res);
    throw new Error(s === "not_member" ? "Your account isn't on this team's list."
      : s === "not_configured" ? "The team list isn't set up yet."
      : `Couldn't save (HTTP ${res.status}). Nothing was changed.`);
  }
  const m = new Map(snap.byBill);
  if (stance) m.set(bill, { stance, updatedAt: new Date().toISOString(), updatedBy: by });
  else m.delete(bill);
  set({ ...snap, byBill: m });
}
