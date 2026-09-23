import { type RefObject, useEffect, useRef } from "react";

const FOCUSABLE = "button, input, select, textarea, a[href], summary, [tabindex]:not([tabindex='-1'])";
const usable = (element: HTMLElement | null): element is HTMLElement =>
  !!element && element.isConnected && !element.matches(":disabled") && (typeof element.checkVisibility !== "function" || element.checkVisibility());

/**
 * Keeps keyboard focus on a screen while its actions run. A button disabled during a request loses focus
 * in the browser, and a control that the refreshed data removes takes the focus with it; either way focus
 * would fall back to the page itself. After an action started on this screen, focus that has fallen to the
 * page returns to the control that had it or, when that control is gone or disabled, to the first control
 * of its nearest remaining container. The member's next pointer or key press ends the watch.
 */
export function useKeepFocus(busy: boolean, root: RefObject<HTMLElement | null>) {
  const last = useRef<HTMLElement | null>(null);
  const trail = useRef<HTMLElement[]>([]);
  const watching = useRef(false);

  useEffect(() => {
    const node = root.current;
    if (!node) return;
    const remember = (event: FocusEvent) => {
      if (!(event.target instanceof HTMLElement)) return;
      last.current = event.target;
      const containers: HTMLElement[] = [];
      for (let parent = event.target.parentElement; parent && parent !== node; parent = parent.parentElement) containers.push(parent);
      trail.current = [...containers, node];
    };
    const release = () => { watching.current = false; };
    node.addEventListener("focusin", remember);
    document.addEventListener("pointerdown", release, true);
    document.addEventListener("keydown", release, true);
    return () => {
      node.removeEventListener("focusin", remember);
      document.removeEventListener("pointerdown", release, true);
      document.removeEventListener("keydown", release, true);
    };
  }, [root]);

  useEffect(() => {
    if (busy && last.current && root.current?.contains(last.current)) watching.current = true;
  }, [busy, root]);

  // After every render while an action's results arrive: focus that fell to the page goes back.
  useEffect(() => {
    if (!watching.current || busy) return;
    const active = document.activeElement;
    if (active && active !== document.body && active.isConnected) return;
    let target = usable(last.current) ? last.current : null;
    for (const container of trail.current) {
      if (target) break;
      if (container.isConnected) target = [...container.querySelectorAll<HTMLElement>(FOCUSABLE)].find(usable) ?? null;
    }
    target?.focus();
  });
}
