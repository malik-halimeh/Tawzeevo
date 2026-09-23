import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useRef } from "react";
import { afterEach, expect, test } from "vitest";

import { useKeepFocus } from "./useKeepFocus";

afterEach(() => { cleanup(); });

/** A screen with one action: Save is disabled while busy, and a result may remove it. */
function Desk({ busy, withSave = true }: { busy: boolean; withSave?: boolean }) {
  const root = useRef<HTMLElement>(null);
  useKeepFocus(busy, root);
  return (
    <section ref={root}>
      <div>
        <input aria-label="Amount" />
        {withSave ? <button disabled={busy} type="button">Save</button> : null}
      </div>
      <button type="button">Other</button>
    </section>
  );
}

// A browser drops focus from a focused control that becomes disabled; jsdom does not (and ignores blur() on a
// disabled control), so these tests drop it just before the action starts.
test("focus that falls to the page while an action runs returns to the control that had it", () => {
  const { rerender } = render(<Desk busy={false} />);
  const save = screen.getByRole("button", { name: "Save" });
  save.focus();
  save.blur();
  rerender(<Desk busy />);
  expect(document.activeElement).toBe(document.body);
  rerender(<Desk busy={false} />);
  expect(save).toHaveFocus();
});

test("when the result removed that control, focus goes to the first control of its nearest remaining container", () => {
  const { rerender } = render(<Desk busy={false} />);
  screen.getByRole("button", { name: "Save" }).focus();
  rerender(<Desk busy />);
  rerender(<Desk busy={false} withSave={false} />);
  expect(screen.getByLabelText("Amount")).toHaveFocus();
});

test("the member's next key press ends the watch, so focus is never taken back", () => {
  const { rerender } = render(<Desk busy={false} />);
  const save = screen.getByRole("button", { name: "Save" });
  save.focus();
  save.blur();
  rerender(<Desk busy />);
  fireEvent.keyDown(document, { key: "Tab" });
  rerender(<Desk busy={false} />);
  expect(document.activeElement).toBe(document.body);
});
