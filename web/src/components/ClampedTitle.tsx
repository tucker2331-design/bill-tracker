// A bill title shown on two lines, with the rest one tap away (owner 2026-11-01: PA titles run to 20+ lines).
// The toggle appears only when the title is actually cut (measured, not guessed from its length). Inside a card that
// is itself a link, the toggle never navigates.
import { useLayoutEffect, useRef, useState } from "react";

export function ClampedTitle({ text, className = "" }: { text: string; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [cut, setCut] = useState(false);
  // A new title (the same box reused for another bill) starts closed and is measured afresh (Gemini #265).
  const [prevText, setPrevText] = useState(text);
  if (text !== prevText) { setPrevText(text); setOpen(false); setCut(false); }
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el || open) return;
    const measure = () => setCut(el.scrollHeight > el.clientHeight + 1);
    measure();
    // Re-measure when the box resizes (a phone rotating, a narrower window): a title that fitted can become cut
    // (Codex #265). ResizeObserver is in every browser the site supports; without it the first measure stands.
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, [text, open]);
  const toggle = (e: React.SyntheticEvent) => { e.preventDefault(); e.stopPropagation(); setOpen((o) => !o); };
  return (
    <div className={className}>
      <div ref={ref} className={open ? "ttl-full" : "ttl-clamp"}>{text}</div>
      {(cut || open) && (
        // A span with button semantics, not a <button>: the War Room card is itself a link, and HTML forbids
        // interactive content inside <a> (Gemini #265). Keyboard: Enter / Space.
        <span role="button" tabIndex={0} className="ttl-more" aria-expanded={open} onClick={toggle}
          onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") toggle(e); }}>
          {open ? "Show less" : "Show full title"}
        </span>
      )}
    </div>
  );
}
