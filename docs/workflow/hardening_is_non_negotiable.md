---
tags: [workflow, feedback, doctrine]
updated: 2026-07-15
status: active
---

# Hardening is non-negotiable — a new direction never leaves in-flight work unhardened

**Owner feedback (2026-07-15), verbatim intent:** *"just because the 'energy' and discussion is around
something doesn't mean we drop the work we are doing and leave unhardened — everything needs to be up to
standard, and a proposal like that concerns me that you don't think that way unless I explicitly state it."*

## The rule
When an exciting new direction appears, it does **not** license pausing, shortcutting, or leaving *any*
in-flight work below standard to chase it. "Where the energy is" is not a reason to trade away hardening.
Standard-quality is the default for everything, always; the owner should never have to re-state it.

## Why this is written down
Fable proposed "pivoting" from the data/trust hardening to the strategic tools. The *framing* implied that
hardening could wait for the more interesting thing — a bad default the owner caught immediately. The
correct framing is additive and sequenced: finish/harden what's in flight to standard, AND pursue the new
direction — never one at the expense of the other, and never a half-hardened surface left behind.

## How to apply
- A "let's pivot to X" that implies dropping Y is wrong; say "we finish/harden Y, and X is the next
  direction" — or if Y genuinely should stop, say so explicitly and get the owner's call ([[workflow/reasoning_doctrine]]
  #4 confirm-before-advance).
- "Done" means hardened to standard (tests, verification, bot fold-in, write-back) — not "the happy path
  works." Gated-for-a-real-reason (can't validate off-season, owner decision pending) is fine and explicit;
  "left rough because we moved on" is not.
- This is a standing default, not a per-task instruction.

See also [[workflow/reasoning_doctrine]], [[ideas/product_identity]] (the "finish VA to gold standard first"
sequencing this protects).
