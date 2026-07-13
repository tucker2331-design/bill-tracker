import { useEffect, useRef, useState } from "react";

// Attach the returned `ref` to a vertically-scrolling element; `hasMore` is true whenever there is content
// BELOW the fold (so a "scroll for more" cue should show) and flips to false at the bottom. Drives the
// visible scroll affordance on the landing feed + the calendar sliver (owner 2026-07-12: the old CSS-only
// scroll-shadow was too subtle to read). Pure display — never touches the data.
//
// Recompute triggers (all three matter — Gemini + CodeRabbit #218, Major):
//   • scroll        — the user moves within the panel;
//   • ResizeObserver — the container's OWN box changes (viewport resize, column reflow);
//   • MutationObserver — the CONTENT changes (feed paged via ← Older/Newer →, or meetings load in async).
// The last one is the one a lone ResizeObserver misses: the panels are height-constrained, so a content
// swap changes `scrollHeight` but NOT the container's outer size, and the cue would go stale on paging.
export function useScrollCue<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [hasMore, setHasMore] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    // 6px slack so sub-pixel rounding at the true bottom doesn't leave the cue stuck on.
    const update = () => setHasMore(el.scrollHeight - el.scrollTop - el.clientHeight > 6);
    update();
    el.addEventListener("scroll", update, { passive: true });
    const ro = new ResizeObserver(update);
    ro.observe(el);
    const mo = new MutationObserver(update);
    mo.observe(el, { childList: true, subtree: true, characterData: true });
    return () => {
      el.removeEventListener("scroll", update);
      ro.disconnect();
      mo.disconnect();
    };
  }, []);
  return { ref, hasMore };
}
