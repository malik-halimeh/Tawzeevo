import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

import { ApplicationRoot } from "./ApplicationRoot";
import i18n from "./i18n";

afterEach(async () => {
  cleanup();
  await i18n.changeLanguage("en");
  document.documentElement.lang = "en";
  document.documentElement.dir = "ltr";
  Object.defineProperty(window, "innerWidth", { configurable: true, value: 1024 });
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
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
    expect(screen.getByRole("heading", { name: "Order received" })).toBeInTheDocument();

    reset.focus();
    expect(reset).toHaveFocus();
    fireEvent.click(reset);
    expect(guest).toHaveAttribute("aria-selected", "true");
  });

  test("filters the synthetic catalog and keeps guest browsing unauthenticated", () => {
    render(<ApplicationRoot demoEnabled pathname="/demo" />);

    expect(screen.getByRole("heading", { name: "Browse the van catalog" })).toBeInTheDocument();
    expect(screen.getByText("Tomato paste")).toBeInTheDocument();
    expect(screen.getByText("Laundry gel")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Home care" }));

    expect(screen.getByText("Laundry gel")).toBeInTheDocument();
    expect(screen.queryByText("Tomato paste")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /sign in|log in|account/i })).not.toBeInTheDocument();
  });

  test("requires guest checkout details and transitions locally to the customer view", () => {
    render(<ApplicationRoot demoEnabled pathname="/demo" />);

    fireEvent.click(screen.getAllByRole("button", { name: /Add to basket/ })[0]!);
    fireEvent.click(screen.getByRole("button", { name: "Review checkout" }));
    fireEvent.click(screen.getByRole("button", { name: "Place preview order" }));

    expect(screen.getByText("Enter name to continue.")).toBeInTheDocument();
    expect(screen.getByText("Enter phone to continue.")).toBeInTheDocument();
    expect(screen.getByText("Enter address to continue.")).toBeInTheDocument();

    fireEvent.change(screen.getByRole("textbox", { name: /^Name/ }), { target: { value: "Maya Saleh" } });
    fireEvent.change(screen.getByRole("textbox", { name: /^Phone/ }), { target: { value: "+961 71 456 789" } });
    fireEvent.change(screen.getByRole("textbox", { name: /^Address/ }), { target: { value: "Achrafieh, Beirut" } });
    fireEvent.click(screen.getByRole("button", { name: "Place preview order" }));

    expect(screen.getByRole("tab", { name: "Customer" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("Maya Saleh")).toBeInTheDocument();
    expect(screen.getByText("+961 71 456 789")).toHaveAttribute("dir", "ltr");
    expect(screen.getByRole("button", { name: "Request cancellation" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Cancel/ })).not.toBeInTheDocument();
    expect(screen.queryByText(/tracking/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /sign in|log in|account/i })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Request cancellation" }));
    expect(screen.getByText("The request is waiting for the owner to approve or reject it.")).toBeInTheDocument();
  });

  test("starts with empty memory state after a fresh mount", () => {
    const firstMount = render(<ApplicationRoot demoEnabled pathname="/demo" />);
    fireEvent.click(screen.getAllByRole("button", { name: /Add to basket/ })[0]!);
    expect(screen.getByText("1 item")).toBeInTheDocument();

    firstMount.unmount();
    render(<ApplicationRoot demoEnabled pathname="/demo" />);

    expect(screen.getByText("0 items")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Review checkout" })).toBeDisabled();
  });

  test("renders Arabic RTL while keeping customer phone text LTR", async () => {
    render(<ApplicationRoot demoEnabled pathname="/demo" />);

    fireEvent.click(screen.getByRole("button", { name: "العربية" }));
    expect(await screen.findByRole("heading", { name: "شاهد توزيـفو من كل محطة." })).toBeInTheDocument();
    expect(document.documentElement).toHaveAttribute("dir", "rtl");

    fireEvent.click(screen.getByRole("tab", { name: "عميل" }));
    const phone = screen.getByText("+961 70 123 456");
    expect(phone).toHaveAttribute("dir", "ltr");
    expect(screen.getByRole("button", { name: "طلب الإلغاء" })).toBeInTheDocument();
  });

  test("presents owner as a tenant membership and builds a synthetic draft", () => {
    render(<ApplicationRoot demoEnabled pathname="/demo" />);

    const guest = screen.getByRole("tab", { name: "Guest" });
    guest.focus();
    fireEvent.keyDown(guest, { key: "ArrowRight" });
    fireEvent.keyDown(screen.getByRole("tab", { name: "Customer" }), { key: "ArrowRight" });

    const ownerTab = screen.getByRole("tab", { name: "Owner" });
    expect(ownerTab).toHaveFocus();
    expect(ownerTab).toHaveAttribute("aria-selected", "true");
    const ownerPanel = screen.getByRole("tabpanel", { name: "Owner" });
    const owner = within(ownerPanel);

    expect(owner.getByText("Client")).toBeInTheDocument();
    expect(owner.getByText("Owner", { selector: "dd" })).toBeInTheDocument();
    expect(owner.getByText("Nadim Khoury · Owner membership")).toBeInTheDocument();
    expect(owner.getByText(/no separate driver account is required/i)).toBeInTheDocument();
    expect(owner.queryByRole("button", { name: /add driver|create driver/i })).not.toBeInTheDocument();

    const phoneInput = owner.getByRole("textbox", { name: "Customer phone" });
    const barcodeInput = owner.getByRole("textbox", { name: "Barcode" });
    expect(phoneInput).toHaveAttribute("dir", "ltr");
    expect(barcodeInput).toHaveValue("5285001234567");

    fireEvent.click(owner.getByRole("button", { name: "Find customer" }));
    expect(owner.getByText("Leila Mansour")).toBeInTheDocument();
    expect(owner.getByText("Grade A")).toBeInTheDocument();

    fireEvent.click(owner.getByRole("button", { name: "Resolve barcode" }));
    expect(owner.getByText("Piece price")).toBeInTheDocument();
    expect(owner.getByText("Box price")).toBeInTheDocument();
    expect(owner.getByText("12 pieces per box")).toBeInTheDocument();
    expect(owner.getByText("5285001234567", { selector: "bdi" })).toBeInTheDocument();

    fireEvent.click(owner.getByRole("button", { name: "Add to draft" }));
    expect(owner.getByText("Draft", { selector: ".status-badge" })).toBeInTheDocument();
    expect(owner.getByText("Tomato paste · 2 pieces")).toBeInTheDocument();
    expect(ownerPanel).not.toHaveTextContent(/confirmed|ledger|posted/i);
  });

  test("renders the compact owner workbench in Arabic with accessible controls", async () => {
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 480 });
    render(<ApplicationRoot demoEnabled pathname="/demo" />);

    fireEvent.click(screen.getByRole("button", { name: "العربية" }));
    expect(await screen.findByRole("tab", { name: "مالك" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "مالك" }));

    const owner = within(screen.getByRole("tabpanel", { name: "مالك" }));
    expect(owner.getByRole("heading", { name: "منضدة عمل المالك" })).toBeInTheDocument();
    expect(owner.getByText("عضوية المنشأة")).toBeInTheDocument();
    expect(owner.getByRole("textbox", { name: "هاتف العميل" })).toHaveAttribute("dir", "ltr");
    expect(owner.getByRole("button", { name: "قراءة الباركود" })).toBeInTheDocument();
  });

  test("limits the driver sheet to assigned work without reassignment controls", () => {
    render(<ApplicationRoot demoEnabled pathname="/demo" />);

    const guest = screen.getByRole("tab", { name: "Guest" });
    guest.focus();
    fireEvent.keyDown(guest, { key: "End" });

    const driverTab = screen.getByRole("tab", { name: "Driver" });
    expect(driverTab).toHaveFocus();
    expect(driverTab).toHaveAttribute("aria-selected", "true");
    const driverPanel = screen.getByRole("tabpanel", { name: "Driver" });
    const driver = within(driverPanel);

    expect(driver.getByText("Driver", { selector: "dd" })).toBeInTheDocument();
    expect(driver.getByText("Samir Rahal")).toBeInTheDocument();
    expect(driver.getByText("2 assigned stops")).toBeInTheDocument();
    expect(driver.getByText("Maya Saleh")).toBeInTheDocument();
    expect(driver.getByText("Karim Nassar")).toBeInTheDocument();
    expect(driver.queryByText("Leila Mansour")).not.toBeInTheDocument();
    expect(driver.queryByText(/profit|supplier|analytics|platform administrator/i)).not.toBeInTheDocument();
    expect(driver.queryByRole("button", { name: /reassign|assign to|manage/i })).not.toBeInTheDocument();
    expect(driverPanel).not.toHaveTextContent(/tracking|map|routing provider/i);

    const detailButtons = driver.getAllByRole("button", { name: "View stop details" });
    fireEvent.click(detailButtons[0]!);
    expect(detailButtons[0]).toHaveAttribute("aria-expanded", "true");
    expect(driver.getByText("+961 71 456 789")).toHaveAttribute("dir", "ltr");
    expect(driver.getByText("INV-1048")).toHaveAttribute("dir", "ltr");
    expect(driver.getByText("Call on arrival and use the main entrance.")).toBeInTheDocument();
  });

  test("renders the compact Arabic driver sheet with accessible assigned-stop details", async () => {
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 360 });
    render(<ApplicationRoot demoEnabled pathname="/demo" />);

    fireEvent.click(screen.getByRole("button", { name: "العربية" }));
    expect(await screen.findByRole("tab", { name: "سائق" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "سائق" }));

    const driver = within(screen.getByRole("tabpanel", { name: "سائق" }));
    expect(driver.getByRole("heading", { name: "ورقة مسار السائق" })).toBeInTheDocument();
    expect(driver.getByText("محطتان مسندتان")).toBeInTheDocument();
    const details = driver.getAllByRole("button", { name: "عرض تفاصيل المحطة" });
    fireEvent.click(details[0]!);
    expect(driver.getByText("+961 71 456 789")).toHaveAttribute("dir", "ltr");
    expect(driver.getByText("INV-1048")).toHaveAttribute("dir", "ltr");
  });

  test("completes the four-perspective journey without network or browser-storage writes", () => {
    const fetchSpy = vi.fn();
    const storageWriteSpy = vi.spyOn(Storage.prototype, "setItem");
    const indexedDbOpenSpy = vi.fn();
    const initialCookie = document.cookie;
    vi.stubGlobal("fetch", fetchSpy);
    vi.stubGlobal("indexedDB", { open: indexedDbOpenSpy });

    render(<ApplicationRoot demoEnabled pathname="/demo" />);
    fireEvent.click(screen.getAllByRole("button", { name: /Add to basket/ })[0]!);
    fireEvent.click(screen.getByRole("tab", { name: "Customer" }));
    fireEvent.click(screen.getByRole("button", { name: "Request cancellation" }));
    fireEvent.click(screen.getByRole("tab", { name: "Owner" }));
    fireEvent.click(screen.getByRole("button", { name: "Find customer" }));
    fireEvent.click(screen.getByRole("button", { name: "Resolve barcode" }));
    fireEvent.click(screen.getByRole("button", { name: "Add to draft" }));
    fireEvent.click(screen.getByRole("tab", { name: "Driver" }));
    fireEvent.click(screen.getAllByRole("button", { name: "View stop details" })[0]!);
    fireEvent.click(screen.getByRole("button", { name: "Reset preview" }));

    expect(fetchSpy).not.toHaveBeenCalled();
    expect(storageWriteSpy).not.toHaveBeenCalled();
    expect(indexedDbOpenSpy).not.toHaveBeenCalled();
    expect(document.cookie).toBe(initialCookie);
    expect(screen.getByRole("tab", { name: "Guest" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("0 items")).toBeInTheDocument();
  });
});
