import { useEffect, useRef, useState } from "react";

// Attach the returned `ref` to a vertically-scrolling element; `hasMore` is true whenever there is content
// BELOW the fold (so a "scroll for more" cue should show) and flips to false at the bottom. Drives the
// visible scroll affordance on the landing feed + the calendar sliver (owner 2026-07-12: the old CSS-only
// scroll-shadow was too subtle to read). Recomputes on scroll AND on resize/content change (ResizeObserver),
// so it stays correct when data loads in or the viewport changes. Pure display — never touches the data.
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
    return () => {
      el.removeEventListener("scroll", update);
      ro.disconnect();
    };
  }, []);
  return { ref, hasMore };
}
