// First-run profile — F3 / M3.
//
// Shown once, after the first sign-in, before anything else. Two things are collected and nothing more:
//
//   1. WHAT TO CALL YOU. The owner's reason, and it is not cosmetic: this name appears beside every
//      interaction on the call sheet ("Tom — Mar 3"), so a teammate reading it needs a person, not an
//      address. Showing emails would also quietly publish everyone's to everyone else on the team.
//
//   2. YOUR DISTRICTS — never your address. The Census lookup below runs in THIS BROWSER, straight to
//      census.gov; the address never touches our servers, so "we do not store addresses" is enforced by
//      topology rather than promised by policy. The user confirms three numbers and those are what persist.
//
// The address box is an ESCAPE HATCH, not the path. Someone who knows their districts types them and never
// sees it. That ordering is deliberate: asking for an address first would make handing one over feel
// required.

import { useState } from "react";
import { lookupDistricts } from "../data/districts";
import { APP_STATE } from "../config";
import { apiFetch, useIdentity } from "../state/auth";

export function FirstRun({ onDone }: { onDone: () => void }) {
  const identity = useIdentity();
  const [name, setName] = useState(identity?.name ?? "");
  const [house, setHouse] = useState("");
  const [senate, setSenate] = useState("");
  const [congress, setCongress] = useState("");
  const [address, setAddress] = useState("");
  const [showLookup, setShowLookup] = useState(false);
  const [looking, setLooking] = useState(false);
  const [lookupErr, setLookupErr] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveErr, setSaveErr] = useState<string | null>(null);

  const doLookup = async () => {
    setLooking(true); setLookupErr(null);
    try {
      const d = await lookupDistricts(address);
      // Fill only what came back. Overwriting a value the user already typed with a blank would be the
      // lookup silently undoing their work.
      if (d.house) setHouse(d.house);
      if (d.senate) setSenate(d.senate);
      if (d.congress) setCongress(d.congress);
      // The address is never stored, and it is not kept in component state past its use either.
      setAddress("");
      if (!d.house && !d.senate && !d.congress) setLookupErr("That matched an address but returned no districts. Enter them below.");
    } catch (e) {
      setLookupErr(e instanceof Error ? e.message : "Lookup failed. Enter your districts below.");
    } finally {
      setLooking(false);
    }
  };

  const save = async () => {
    setSaving(true); setSaveErr(null);
    try {
      const res = await apiFetch("/api/me", {
        method: "PUT",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          display_name: name.trim(),
          home_state: APP_STATE,
          district_house: house.trim(),
          district_senate: senate.trim(),
          district_congress: congress.trim(),
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.error || `Save failed (HTTP ${res.status})`);
      }
      onDone();
    } catch (e) {
      // Never close on failure: silently dismissing would lose what they typed and leave the profile unset.
      setSaveErr(e instanceof Error ? e.message : "Could not save.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="cardwrap">
      <div className="card fr-card" onClick={(e) => e.stopPropagation()}>
        <h2 className="fr-h">Welcome — two quick things</h2>

        <label className="fr-field">
          <span className="fr-label">What should we call you?</span>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="First name"
                 autoFocus maxLength={60} />
          <span className="fr-hint">Shown to your team beside anything you log.</span>
        </label>

        <div className="fr-field">
          <span className="fr-label">Your districts</span>
          <div className="fr-districts">
            <label><span>House</span>
              <input value={house} onChange={(e) => setHouse(e.target.value)} inputMode="numeric" maxLength={4} /></label>
            <label><span>Senate</span>
              <input value={senate} onChange={(e) => setSenate(e.target.value)} inputMode="numeric" maxLength={4} /></label>
            <label><span>Congress</span>
              <input value={congress} onChange={(e) => setCongress(e.target.value)} inputMode="numeric" maxLength={4} /></label>
          </div>

          {!showLookup ? (
            <button className="fr-link" onClick={() => setShowLookup(true)}>I don't know my districts</button>
          ) : (
            <div className="fr-lookup">
              <span className="fr-hint">
                Looked up in your browser, straight from the Census Bureau. The address is not sent to us and
                is not saved anywhere.
              </span>
              <div className="fr-lookup-row">
                <input value={address} onChange={(e) => setAddress(e.target.value)}
                       placeholder="Street, city, state" />
                <button className="fr-btn" onClick={doLookup} disabled={looking || !address.trim()}>
                  {looking ? "Looking…" : "Look up"}
                </button>
              </div>
              {lookupErr && <span className="fr-err">{lookupErr}</span>}
            </div>
          )}
        </div>

        {saveErr && <p className="fr-err">{saveErr}</p>}

        <div className="fr-foot">
          <span className="fr-hint">Used for legislative advocacy optimization.</span>
          <button className="fr-btn fr-primary" onClick={save} disabled={saving || !name.trim()}>
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}
