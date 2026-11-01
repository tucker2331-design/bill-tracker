// A bill title shown on two lines, with the rest one tap away (owner 2026-11-01: PA titles run to 20+ lines).
// The toggle appears only when the title is actually cut (measured, not guessed from its length). Inside a card that
// is itself a link, the toggle never navigates.
import { useLayoutEffect, useRef, useState } from "react";

export function ClampedTitle({ text, className = "" }: { text: string; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [cut, setCut] = useState(false);
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
  const toggle = (e: React.MouseEvent) => { e.preventDefault(); e.stopPropagation(); setOpen((o) => !o); };
  return (
    <div className={className}>
      <div ref={ref} className={open ? "ttl-full" : "ttl-clamp"}>{text}</div>
      {(cut || open) && (
        <button type="button" className="ttl-more" onClick={toggle} aria-expanded={open}>
          {open ? "Show less" : "Show full title"}
        </button>
      )}
    </div>
  );
}
