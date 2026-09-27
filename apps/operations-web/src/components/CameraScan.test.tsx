import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import i18n from "../i18n";
import { CameraScanButton } from "./CameraScan";

const decode = vi.fn();
vi.mock("@zxing/browser", () => ({
  BrowserMultiFormatReader: class { decodeFromConstraints = decode; },
}));

beforeEach(async () => { await i18n.changeLanguage("en"); decode.mockReset(); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

const withCamera = () => vi.stubGlobal("navigator", { ...navigator, mediaDevices: { getUserMedia: vi.fn() } });

test("a read barcode is handed over, the camera stops and the form is submitted (D-113)", async () => {
  withCamera();
  const stop = vi.fn();
  decode.mockImplementation((_constraints: unknown, _video: unknown, callback: (result: { getText: () => string }, error: unknown, controls: { stop: () => void }) => void) => {
    setTimeout(() => callback({ getText: () => "5280000000012" }, undefined, { stop }), 0);
    return Promise.resolve({ stop });
  });
  const scanned = vi.fn();
  const submitted = vi.fn((event: Event) => event.preventDefault());
  render(<form onSubmit={(event) => submitted(event.nativeEvent)}><CameraScanButton onScan={scanned} /></form>);
  expect(decode).not.toHaveBeenCalled(); // nothing is loaded or asked before the click
  fireEvent.click(screen.getByRole("button", { name: "Scan with camera" }));
  await waitFor(() => expect(scanned).toHaveBeenCalledWith("5280000000012"));
  expect(stop).toHaveBeenCalled();
  await waitFor(() => expect(submitted).toHaveBeenCalled());
  expect(screen.queryByLabelText("Camera preview")).not.toBeInTheDocument();
});

test("a refused permission and a device without a camera each say so", async () => {
  withCamera();
  decode.mockRejectedValue(new DOMException("denied", "NotAllowedError"));
  render(<CameraScanButton onScan={vi.fn()} />);
  fireEvent.click(screen.getByRole("button", { name: "Scan with camera" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Camera access was refused");
  cleanup();

  vi.stubGlobal("navigator", { ...navigator, mediaDevices: undefined });
  render(<CameraScanButton onScan={vi.fn()} />);
  fireEvent.click(screen.getByRole("button", { name: "Scan with camera" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("No camera was found on this device");
});
