// "Contacts" on the bill card: who from the team reached out, when, and a note. Quiet by default — a short list and
// one "Log a contact" link; the three-field form only appears when asked for. Every row is the team's own entry,
// labelled as such (P20a), never styled like LIS data.
import { useEffect, useState } from "react";
import { useIdentity } from "../state/auth";
import { addContact, loadContacts, todayLocal, type ContactsResult } from "../state/contacts";

const shortDate = (iso: string) => {
  const d = new Date(`${iso}T00:00:00`);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
};

export function ContactLog({ bill, sessionCode }: { bill: string; sessionCode: string }) {
  const identity = useIdentity();
  const [res, setRes] = useState<ContactsResult | undefined>(undefined);
  const [tick, setTick] = useState(0);
  const [open, setOpen] = useState(false);
  const [actor, setActor] = useState(identity?.name ?? "");
  const [day, setDay] = useState(todayLocal());
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    let alive = true;
    loadContacts(sessionCode, bill).then((r) => { if (alive) setRes(r); });
    return () => { alive = false; };
  }, [bill, sessionCode, tick]);

  const save = async () => {
    setErr(""); setSaving(true);
    try {
      await addContact(sessionCode, bill, { actor: actor.trim(), occurredOn: day, note: note.trim() });
      setNote(""); setOpen(false); setTick((t) => t + 1);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Couldn't save. Nothing was changed.");
    } finally {
      setSaving(false);
    }
  };

  let list;
  if (res === undefined) list = <p className="muted cl-empty">Loading…</p>;
  else if (res.status !== "ok") list = <p className="muted cl-empty">{
    res.status === "not_member" ? "Your account isn't on this team's list."
      : res.status === "not_configured" ? "The team list isn't set up yet." : "Couldn't load contacts."}</p>;
  else if (res.contacts.length === 0) list = <p className="muted cl-empty">No one has logged a contact yet.</p>;
  else list = (
    <ul className="cl-list">
      {res.contacts.map((c) => (
        <li key={c.id}>
          <span className="cl-who">{c.actor}</span>
          <span className="muted cl-when">{shortDate(c.occurredOn)}</span>
          <span className="cl-note">{c.note}</span>
        </li>
      ))}
    </ul>
  );

  const canWrite = res?.status === "ok";
  return (
    <section className="cl" aria-label="Contacts">
      <div className="cl-head">
        <h3 className="h">Contacts</h3>
        {canWrite && !open && <button type="button" className="gtoggle" onClick={() => setOpen(true)}>Log a contact</button>}
      </div>
      {open && (
        <form className="cl-form" onSubmit={(e) => { e.preventDefault(); void save(); }}>
          <label htmlFor="cl-actor">Who
            <input id="cl-actor" value={actor} onChange={(e) => setActor(e.target.value)} maxLength={80} required />
          </label>
          <label htmlFor="cl-day">When
            <input id="cl-day" type="date" value={day} max={todayLocal()} onChange={(e) => setDay(e.target.value)} required />
          </label>
          <label htmlFor="cl-note" className="cl-note-field">Note
            <textarea id="cl-note" value={note} onChange={(e) => setNote(e.target.value)} maxLength={2000} rows={2}
              placeholder="Who you spoke with and what they said" required />
          </label>
          <div className="cl-actions">
            <button type="submit" className="cl-save" disabled={saving || !actor.trim() || !note.trim() || !day}>
              {saving ? "Saving…" : "Save"}
            </button>
            <button type="button" className="gtoggle" onClick={() => { setOpen(false); setErr(""); }}>Cancel</button>
            {err && <span className="cl-err">{err}</span>}
          </div>
        </form>
      )}
      {list}
      <p className="muted cl-foot">Your team's entries, not from LIS.</p>
    </section>
  );
}
