import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

import { ApplicationRoot } from "./ApplicationRoot";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("isolated demo boot path", () => {
  test("renders outside authentication without making a network request", () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);

    render(<ApplicationRoot demoEnabled pathname="/demo" />);

    expect(screen.getByRole("heading", { name: "See Tawzeevo from every stop." })).toBeInTheDocument();
    expect(screen.getByText("Nothing on this page is saved or sent.")).toBeInTheDocument();
    expect(screen.queryByText("Restoring your secure session…")).not.toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  test("keeps the preview unavailable when its build flag is disabled", () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);

    render(<ApplicationRoot demoEnabled={false} pathname="/demo" />);

    expect(screen.getByRole("heading", { name: "Preview unavailable" })).toBeInTheDocument();
    expect(screen.queryByRole("tablist")).not.toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  test("supports named keyboard role controls and reset behavior", () => {
    render(<ApplicationRoot demoEnabled pathname="/demo" />);

    const guest = screen.getByRole("tab", { name: "Guest" });
    const customer = screen.getByRole("tab", { name: "Customer" });
    const reset = screen.getByRole("button", { name: "Reset preview" });

    guest.focus();
    fireEvent.keyDown(guest, { key: "ArrowRight" });
    expect(customer).toHaveFocus();
    expect(customer).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel")).toHaveTextContent("supplied checkout details");

    reset.focus();
    expect(reset).toHaveFocus();
    fireEvent.click(reset);
    expect(guest).toHaveAttribute("aria-selected", "true");
  });
});
