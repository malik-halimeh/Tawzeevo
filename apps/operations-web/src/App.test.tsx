import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, test } from "vitest";

import { App } from "./App";
import "./i18n";

test("renders the Tawzeevo operations foundation", () => {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );

  expect(screen.getByRole("link", { name: "Tawzeevo" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: /Cash Van workspace/i })).toBeInTheDocument();
});
