import type { KeyboardEvent } from "react";

import "../../listKit.css";

export type Chip<T extends string> = { value: T; label: string; count?: number | undefined };

type Selection<T extends string> =
  | { multiple?: false; value: T; onChange: (value: T) => void }
  | { multiple: true; value: readonly T[]; onChange: (value: T[]) => void };

/**
 * One row of filter chips that scrolls sideways on a phone. Each chip is a toggle button
 * (`aria-pressed`); one chip is chosen at a time unless `multiple` is set. Left/Right arrows move
 * between chips in reading direction.
 */
export function ChipRow<T extends string>({ label, chips, ...selection }: { label: string; chips: readonly Chip<T>[] } & Selection<T>) {
  const pressed = (value: T) => (selection.multiple ? selection.value.includes(value) : selection.value === value);

  function toggle(value: T) {
    if (!selection.multiple) {
      if (value !== selection.value) selection.onChange(value);
      return;
    }
    selection.onChange(selection.value.includes(value) ? selection.value.filter((item) => item !== value) : [...selection.value, value]);
  }

  function onKey(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight" && event.key !== "Home" && event.key !== "End") return;
    const buttons = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>("button:not(:disabled)"));
    const current = buttons.indexOf(document.activeElement as HTMLButtonElement);
    if (current < 0) return;
    const rtl = event.currentTarget.closest("[dir]")?.getAttribute("dir") === "rtl";
    const forward = (event.key === "ArrowRight") !== rtl;
    const next = event.key === "Home" ? 0 : event.key === "End" ? buttons.length - 1 : Math.min(buttons.length - 1, Math.max(0, current + (forward ? 1 : -1)));
    event.preventDefault();
    buttons[next]?.focus();
  }

  return (
    <div aria-label={label} className="chip-row" onKeyDown={onKey} role="group">
      {chips.map((chip) => (
        <button aria-pressed={pressed(chip.value)} className="chip" key={chip.value} onClick={() => toggle(chip.value)} type="button">
          {chip.label}
          {chip.count !== undefined ? <>{" "}<bdi className="chip-count" dir="ltr">{chip.count}</bdi></> : null}
        </button>
      ))}
    </div>
  );
}
