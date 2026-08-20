import React from "react";
import ReactDOM from "react-dom/client";

import { ApplicationRoot } from "./ApplicationRoot";
import { isDemoPath } from "./demo/demoPath";
import "./styles.css";

const demoEnabled = import.meta.env.VITE_DEMO_PREVIEW === "true";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ApplicationRoot demoEnabled={demoEnabled} />
  </React.StrictMode>,
);

if ("serviceWorker" in navigator && import.meta.env.PROD && !(demoEnabled && isDemoPath(window.location.pathname))) {
  window.addEventListener("load", () => {
    void navigator.serviceWorker.register("/sw.js");
  });
}
