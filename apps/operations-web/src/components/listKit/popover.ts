import { type KeyboardEvent, type RefObject, useEffect, useRef } from "react";

const FOCUSABLE = 'a[href], button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])';

export function focusables(container: HTMLElement | null): HTMLElement[] {
  if (!container) return [];
  // Sorted explicitly: some selector engines return a selector list grouped by selector, not in page order.
  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE)).sort((a, b) => (a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1));
}

/** Arrow keys (and Home/End) move focus between the controls of a small menu; returns whether the key was used. */
export function moveFocusWithArrows(event: KeyboardEvent, container: HTMLElement | null): boolean {
  const items = focusables(container);
  if (!items.length) return false;
  const current = items.indexOf(document.activeElement as HTMLElement);
  let next: number;
  if (event.key === "ArrowDown") next = current < 0 ? 0 : (current + 1) % items.length;
  else if (event.key === "ArrowUp") next = current < 0 ? items.length - 1 : (current - 1 + items.length) % items.length;
  else if (event.key === "Home") next = 0;
  else if (event.key === "End") next = items.length - 1;
  else return false;
  event.preventDefault();
  items[next]?.focus();
  return true;
}

/**
 * A small panel opened from a trigger button: focuses its first control (or `initialFocus`) when it
 * opens and closes when the pointer goes down outside it or focus moves outside it. Escape is handled
 * by the panel's own key handler so focus can return to the trigger.
 */
export function usePopover({ open, onDismiss, trigger, panel, initialFocus }: {
  open: boolean;
  onDismiss: () => void;
  trigger: RefObject<HTMLElement | null>;
  panel: RefObject<HTMLElement | null>;
  initialFocus?: () => HTMLElement | null | undefined;
}) {
  const dismiss = useRef(onDismiss);
  const firstFocus = useRef(initialFocus);
  useEffect(() => { dismiss.current = onDismiss; firstFocus.current = initialFocus; });
  useEffect(() => {
    if (!open) return;
    (firstFocus.current?.() ?? focusables(panel.current)[0])?.focus();
    const outside = (target: EventTarget | null) => target instanceof Node && !panel.current?.contains(target) && !trigger.current?.contains(target);
    const onPointer = (event: Event) => { if (outside(event.target)) dismiss.current(); };
    // A control that replaces itself (an inline confirmation) drops focus to the body for a moment;
    // only focus that lands on something else outside the panel closes it.
    const onFocus = (event: FocusEvent) => { if (outside(event.target)) dismiss.current(); };
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("focusin", onFocus);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("focusin", onFocus);
    };
  }, [open, panel, trigger]);
}
