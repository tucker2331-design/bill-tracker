// The team's contact log for a bill — who reached out, when, and a note (owner 2026-09-28: "a simple name date and
// note so whoever is using knows who contacted"). ORG-ASSERTED: typed by the team, verified by nobody, and shown
// as such. Stored in D1 behind the Worker (sign-in + team list).
import { APP_STATE } from "../config";
import { apiFetch } from "./auth";

export interface Contact {
  id: number;
  actor: string;        // who made the contact, as typed
  occurredOn: string;   // YYYY-MM-DD
  note: string;
  createdBy: string;    // verified email of whoever logged it
}

/** "ok" | the team gate's reasons | "error" — each gets its own sentence on screen, never "no contacts". */
export type ContactsResult =
  | { status: "ok"; contacts: Contact[] }
  | { status: "not_member" | "not_configured" | "error" };

async function gateStatus(res: Response): Promise<"not_member" | "not_configured" | "error"> {
  if (res.status !== 403) return "error";
  const b = await res.json().catch(() => null);
  return b?.reason === "not_configured" ? "not_configured" : "not_member";
}

export async function loadContacts(session: string, bill: string): Promise<ContactsResult> {
  try {
    const q = new URLSearchParams({ state: APP_STATE, session, bill_number: bill });
    const res = await apiFetch(`/api/interactions?${q.toString()}`, { cache: "no-store" });
    if (!res.ok) return { status: await gateStatus(res) };
    const body = await res.json();
    const contacts: Contact[] = (body?.interactions ?? []).map((r: Record<string, unknown>) => ({
      id: Number(r.id), actor: String(r.actor ?? ""), occurredOn: String(r.occurred_on ?? ""),
      note: String(r.note ?? ""), createdBy: String(r.created_by ?? ""),
    }));
    return { status: "ok", contacts };
  } catch (e) {
    console.warn("Contacts: load failed", e);
    return { status: "error" };
  }
}

/** Resolves only once the server has stored the row; rejects with a sentence the form can show. */
export async function addContact(session: string, bill: string, c: { actor: string; occurredOn: string; note: string }): Promise<void> {
  const res = await apiFetch("/api/interactions", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ state: APP_STATE, session_code: session, bill_number: bill,
                           occurred_on: c.occurredOn, actor: c.actor, note: c.note }),
  });
  if (res.ok) return;
  if (res.status === 400) {
    const b = await res.json().catch(() => null);
    throw new Error(b?.error ? `Not saved: ${b.error}.` : "Not saved: the entry was incomplete.");
  }
  const s = await gateStatus(res);
  throw new Error(s === "not_member" ? "Your account isn't on this team's list."
    : s === "not_configured" ? "The team list isn't set up yet."
    : `Couldn't save (HTTP ${res.status}). Nothing was changed.`);
}

/** Today in the user's own timezone, as YYYY-MM-DD (not UTC: an evening call must not land on tomorrow). */
export function todayLocal(d = new Date()): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}
