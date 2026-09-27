import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

/**
 * "Scan with camera" (D-113). The scanner library (@zxing/browser, MIT; see THIRD_PARTY_NOTICES.md)
 * is loaded only when the button is pressed, and the camera is asked for only then. A read barcode
 * is handed to `onScan`, exactly as if it had been typed; the camera stops at once.
 */
type Problem = "denied" | "noCamera" | "failed";

export function CameraScanButton({ onScan, autoSubmit = true }: { onScan: (barcode: string) => void; autoSubmit?: boolean }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [problem, setProblem] = useState<Problem>();
  const video = useRef<HTMLVideoElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const handler = useRef(onScan);
  useEffect(() => { handler.current = onScan; });

  useEffect(() => {
    if (!open) return;
    let stopped = false;
    let controls: { stop: () => void } | undefined;
    const start = async () => {
      if (!navigator.mediaDevices?.getUserMedia) { setProblem("noCamera"); setOpen(false); return; }
      try {
        const { BrowserMultiFormatReader } = await import("@zxing/browser");
        if (stopped || !video.current) return;
        const reader = new BrowserMultiFormatReader();
        controls = await reader.decodeFromConstraints({ video: { facingMode: "environment" } }, video.current, (result, _error, active) => {
          if (!result) return;
          active.stop();
          setOpen(false);
          handler.current(result.getText());
          // Submit the surrounding form once the value is on screen, as pressing its button would.
          if (autoSubmit) requestAnimationFrame(() => button.current?.closest("form")?.requestSubmit());
        });
        if (stopped) controls.stop();
      } catch (caught) {
        const name = caught instanceof DOMException || caught instanceof Error ? caught.name : "";
        setProblem(name === "NotAllowedError" || name === "SecurityError" ? "denied" : name === "NotFoundError" || name === "OverconstrainedError" ? "noCamera" : "failed");
        setOpen(false);
      }
    };
    void start();
    return () => { stopped = true; controls?.stop(); };
  }, [open, autoSubmit]);

  return (
    <span className="camera-scan">
      <button aria-expanded={open} className="button button-secondary" ref={button} onClick={() => { setProblem(undefined); setOpen(!open); }} type="button">
        {open ? t("camera.stop") : t("camera.scan")}
      </button>
      {open ? <video aria-label={t("camera.preview")} className="camera-preview" muted playsInline ref={video} /> : null}
      {problem ? <span className="field-error" role="alert">{t(`camera.${problem}`)}</span> : null}
    </span>
  );
}
