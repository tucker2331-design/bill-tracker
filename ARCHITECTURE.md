# 🏛️ SYSTEM ARCHITECTURE & ENGINEERING MANIFESTO
**Project:** Enterprise Legislative Intelligence Platform
**Standard:** Bank-Grade / Mission Critical (Tier 1)

## 0. THE PRIME DIRECTIVE
This system processes real-time legislative data that dictates the deployment of lobbying capital. **Treat every bill movement like a wire transfer.** * **Zero Assumptions:** Never guess missing data or infer physical locations from unreadable text.
* **No Silent Failures:** If a state's data drops a packet, the system MUST scream. A visible error is infinitely safer than a quiet lie.
* **Decoupled by Default:** The core processing engine must know nothing about the specific state, the data source type (CSV, JSON, XML), or the storage database. 

---

## 1. THE DECOUPLED MULTI-STATE ARCHITECTURE (SCALABILITY)
To scale nationally and allow modular infrastructure upgrades (e.g., migrating from Google Sheets to an enterprise Postgres database), the codebase MUST adhere to the **Adapter/Interface Design Pattern**.

### 1.1 The Core Engine (State-Agnostic)
* The `State Machine` and `Transaction Protocol` live here. 
* It accepts a standardized `NormalizedEvent` object and outputs a `StateTransaction`.
* It does NOT contain hardcoded rules for specific states.

### 1.2 State Extractors (The Adapters)
* Each state (e.g., Virginia, Maryland) gets its own Adapter.
* Adapters are responsible for hitting state-specific endpoints, handling state-specific rate limits, mapping local jargon to Canonical IDs via a config file, and translating the raw feed into a `NormalizedEvent`.

### 1.3 Storage Interfaces (The Loaders)
* The engine pushes data via a `StorageInterface`. 
* Infrastructure upgrades (like moving to AWS RDS) should only require writing a new Adapter, leaving the core engine completely untouched.

### 1.4 Macro Analytics & Telemetry Layer
* Because all state data is mapped to `NormalizedEvents` and `Canonical_IDs`, the system must emit normalized telemetry. 
* This allows for cross-state statistical analysis (e.g., querying the average time a bill spends in a "Finance" committee in VA versus MD).

---

## 2. RESILIENCE, AUDITING, & RECOVERY
State legislative databases are notoriously unstable. Our platform must be invincible to upstream outages and human errors.

### 2.1 The Bug Ledger (Observability)
* Errors, parsing failures, and dropped packets do not just trigger UI flags; they must be persistently logged to a dedicated `Bug_Logs` datastore.
* This creates an immutable audit trail for human triage and allows us to track the degradation of state data quality over time.

### 2.2 State Caching & Cold-Boot Recovery
* The system must never rely 100% on live upstream state APIs being available. 
* It must maintain a persistent local cache (`API_Cache` / `State_Ledger`). 
* If a state API goes offline, the system must be able to run seamlessly off its backups, calculating deltas rather than requiring a full refresh.

---

## 3. THE ZERO-ASSUMPTION ENGINE (EVENT SOURCING)
The core engine rebuilds the tracking calendar chronologically. Every event is an immutable transaction.

### 3.1 The 4-Step Transaction Protocol
Every event must pass through these explicit steps:
1. **Entity Resolution:** Map raw text to a normalized `Canonical_ID`. No fuzzy preposition guessing.
2. **Action Scope:** Classify the verb strictly as *Routing* (moves target), *Escalation* (moves to Floor), *Terminal* (stays in place), or *Absolute Macro* (forces Floor/Exec reset).
3. **Visual Router:** Determine the UI presentation bucket based on the Action Scope.
4. **State Ledger:** Update the backend memory for the *next* chronological sequence.

### 3.2 Temporal Boundaries & Session Partitioning
* Historical processing is strictly isolated from future predictions. The engine may only query contextual data from the exact date of the event being processed.
* State memory keys MUST combine Session ID + Bill ID (e.g., `2026_HB100`) to prevent data bleed across legislative years.

---

## 4. THE LOUD FAILURE PROTOCOLS
We expect clerks to make typos and packets to drop. The system must operationalize these failures.

### 4.1 The Double-Entry Mismatch Flag
* **Trigger:** A Terminal/Status event explicitly names a location that conflicts with the bill's current backend memory.
* **Action:** Log the event in the newly discovered room, update memory, and explicitly flag the discontinuity on the UI: `⚠️ [Mismatch Detected: Origin State was X]`.

### 4.2 The Limbo Protocol & Dead Letter Queue (DLQ)
* **Trigger:** Entity is Unmapped and Verb is unreadable.
* **Action:** Do NOT default to the last known location. Route memory to `STATE_TRIAGE`, flag the UI, and fire a payload to the DLQ/Bug Ledger for immediate human review.

---

## 5. STRICT CODING STANDARDS
Any pull request violating these rules will be rejected.

* **[ANTI-PATTERN 01] Silent Exceptions:** `try: ... except Exception: pass` is strictly banned in chronological processing loops. Exceptions must be caught, routed to the DLQ, and logged.
* **[ANTI-PATTERN 02] Blind State Wipes:** Do not wipe the storage database and rewrite from scratch. Read the existing cache, calculate deltas, and execute updates to preserve human-entered data and survive upstream outages.
* **[ANTI-PATTERN 03] Naive Time:** Datetimes must always be timezone-aware. "Current Date" must be parameterizable for historical unit testing.
* **[ANTI-PATTERN 04] UI Payload Shattering:** All final text outcomes bound for the UI must be passed through a length-limiter to prevent large text blocks from breaking downstream visual layouts.
* **[ANTI-PATTERN 05] State Splintering (Atomic Transitions):** A bill entity can only exist in one state/location at a given time. Pipeline sequencing must resolve multiple intraday events into a single, definitive final state to prevent duplicate cards fracturing across the UI.
* **[ANTI-PATTERN 06] Collapsing UI Views:** The 7-Day Kanban board layout is a fixed enterprise view. It MUST remain persistently visible and structurally intact, even if a specific day has zero active legislative events.
