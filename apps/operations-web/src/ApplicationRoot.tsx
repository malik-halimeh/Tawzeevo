import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";

import { App } from "./App";
import { AuthProvider } from "./auth/AuthContext";
import { DemoGallery } from "./demo/DemoGallery";
import { isDemoPath } from "./demo/demoPath";
import "./i18n";

const queryClient = new QueryClient();

function DemoUnavailable() {
  return (
    <main className="demo-unavailable">
      <span>404</span>
      <h1>Preview unavailable</h1>
      <p>The isolated role preview is not enabled in this build.</p>
      <a className="button" href="/">Return to Tawzeevo</a>
    </main>
  );
}

interface ApplicationRootProps {
  demoEnabled?: boolean;
  pathname?: string;
}

export function ApplicationRoot({
  demoEnabled = import.meta.env.VITE_DEMO_PREVIEW === "true",
  pathname = window.location.pathname,
}: ApplicationRootProps) {
  if (isDemoPath(pathname)) {
    return demoEnabled ? <DemoGallery /> : <DemoUnavailable />;
  }

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <App />
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
