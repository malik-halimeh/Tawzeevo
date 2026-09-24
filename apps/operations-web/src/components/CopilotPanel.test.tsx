import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";

import type { CopilotResponse } from "../api/intelligence";
import i18n from "../i18n";
import { CopilotPanel } from "./CopilotPanel";

afterEach(async () => { cleanup(); vi.unstubAllGlobals(); await i18n.changeLanguage("en"); });

const CONFIGURED = { configured: true, provider: "groq", model: "test-model" };

function reply(overrides: Partial<CopilotResponse> = {}): CopilotResponse {
  return {
    conversation_id: "11111111-1111-4111-8111-111111111111",
    answer: "Call **Tyre Fresh Foods** first: 640.50 USD is overdue.\n\n- Then Byblos Grocery, who stopped buying.",
    conversation_text: "Call **C-TYRE01** first: 640.50 USD is overdue.\n\n- Then C-BYB002, who stopped buying.",
    references: [
      { ref: "C-TYRE01", customer_id: "c-tyre", customer_name: "Tyre Fresh Foods" },
      { ref: "C-BYB002", customer_id: "c-byblos", customer_name: "Byblos Grocery" },
    ],
    grounding: [{ tool: "get_daily_priorities", period: null, currency: "USD", ok: true }, { tool: "get_period_overview", period: "30d", currency: null, ok: true }],
    warnings: [],
    unverified_numbers: [],
    ...overrides,
  };
}

interface Sent { message: string; conversation: { role: string; content: string }[]; conversation_id?: string }

function stubAssistant(status: unknown, answers: (Response | (() => Response))[]) {
  const sent: Sent[] = [];
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = input instanceof Request ? input.url : input.toString();
    if (url.includes("/intelligence/copilot/status?tenant_id=t1")) return Promise.resolve(Response.json(status));
    if (url.includes("/intelligence/copilot/query?tenant_id=t1") && init?.method === "POST") {
      sent.push(JSON.parse(init.body as string) as Sent);
      const next = answers.shift();
      return Promise.resolve(typeof next === "function" ? next() : next ?? Response.json(reply()));
    }
    return Promise.resolve(Response.json({ detail: { code: "NOT_FOUND", message: url } }, { status: 404 }));
  }));
  return sent;
}

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter><CopilotPanel tenantId="t1" /></MemoryRouter></QueryClientProvider>);
}

test("without a provider the assistant says it is not switched on and points to the figures that still work", async () => {
  const sent = stubAssistant({ configured: false, provider: null, model: null }, []);
  renderPanel();
  expect(await screen.findByText("The assistant is not switched on")).toBeInTheDocument();
  expect(screen.getByText(/Everything else keeps working without it/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "See today's priorities" })).toHaveAttribute("href", "/workspace?tenant=t1&section=customers");
  expect(screen.getByRole("link", { name: "Open Analytics" })).toHaveAttribute("href", "/workspace?tenant=t1&section=analytics");
  expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  expect(sent).toEqual([]);
});

test("a suggested question gets an answer with its customers, its sources and no raw markup; a follow-up carries the history", async () => {
  const sent = stubAssistant(CONFIGURED, [Response.json(reply()), Response.json(reply({ answer: "Nothing else is overdue.", conversation_text: "Nothing else is overdue.", references: [], grounding: [{ tool: "get_customer_debts", period: null, currency: "USD", ok: true }] }))]);
  renderPanel();
  fireEvent.click(await screen.findByRole("button", { name: "Who should I call today?" }));
  const thread = await screen.findByRole("list", { name: "Conversation" });
  await waitFor(() => expect(thread).toHaveTextContent("Call Tyre Fresh Foods first: 640.50 USD is overdue."));
  expect(thread.textContent).not.toContain("**");
  expect(within(thread).getByText("Then Byblos Grocery, who stopped buying.").tagName).toBe("LI");
  expect(within(thread).getByRole("link", { name: "Tyre Fresh Foods" })).toHaveAttribute("href", "/workspace?tenant=t1&section=customers&customer=c-tyre");
  expect(thread).toHaveTextContent("Based on:Today's priorities · USDPeriod figures · Last 30 days");
  expect(sent[0]).toEqual({ message: "Who should I call today?", conversation: [] });

  fireEvent.change(screen.getByRole("textbox", { name: "Your question" }), { target: { value: "Anyone else?" } });
  fireEvent.click(screen.getByRole("button", { name: "Ask" }));
  await waitFor(() => expect(thread).toHaveTextContent("Nothing else is overdue."));
  // The history sent back is the reference form the provider wrote, never the resolved names.
  expect(sent[1]).toEqual({
    message: "Anyone else?",
    conversation: [{ role: "user", content: "Who should I call today?" }, { role: "assistant", content: reply().conversation_text }],
    conversation_id: "11111111-1111-4111-8111-111111111111",
  });
  expect(JSON.stringify(sent[1])).not.toContain("Tyre Fresh Foods");

  fireEvent.click(screen.getByRole("button", { name: "New conversation" }));
  expect(screen.queryByRole("list", { name: "Conversation" })).not.toBeInTheDocument();
  expect(screen.getByText("Try asking:")).toBeInTheDocument();
});

test("figures the tools did not return, and answers without any tool, are flagged rather than trusted", async () => {
  stubAssistant(CONFIGURED, [Response.json(reply({ answer: "You will collect 9999 USD.", warnings: ["UNVERIFIED_NUMBERS", "NO_TOOL_USED"], unverified_numbers: ["9999"], grounding: [], references: [] }))]);
  renderPanel();
  fireEvent.change(await screen.findByRole("textbox", { name: "Your question" }), { target: { value: "How much will I collect?" } });
  fireEvent.click(screen.getByRole("button", { name: "Ask" }));
  const notes = await screen.findAllByRole("note");
  expect(notes[0]!.textContent?.replace(/[⁦-⁩]/g, "")).toBe("Check these figures before relying on them: 9999. They were not found in the Tawzeevo data used for this answer.");
  expect(notes[1]).toHaveTextContent("This answer did not use any Tawzeevo figures");
  expect(screen.queryByText("Based on:")).not.toBeInTheDocument();
});

test("a provider failure is explained and the same question can be asked again", async () => {
  const sent = stubAssistant(CONFIGURED, [
    Response.json({ detail: { code: "COPILOT_PROVIDER_UNAVAILABLE", message: "The business assistant is unavailable (TIMEOUT)" } }, { status: 502 }),
    Response.json(reply({ answer: "Tyre Fresh Foods owes the most." })),
  ]);
  renderPanel();
  fireEvent.change(await screen.findByRole("textbox", { name: "Your question" }), { target: { value: "Who owes the most?" } });
  fireEvent.click(screen.getByRole("button", { name: "Ask" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("did not answer in time. Your data is unchanged");
  fireEvent.click(screen.getByRole("button", { name: "Ask again" }));
  expect(await screen.findByText("Tyre Fresh Foods owes the most.")).toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(sent.map((body) => body.message)).toEqual(["Who owes the most?", "Who owes the most?"]);
  expect(sent[1]!.conversation).toEqual([]); // the failed turn is not sent as history
});

test("a rate limit reads as a pause, and a provider switched off mid-session shows the setup state", async () => {
  stubAssistant(CONFIGURED, [
    Response.json({ detail: { code: "COPILOT_RATE_LIMITED", message: "Too many" } }, { status: 429 }),
    Response.json({ detail: { code: "COPILOT_NOT_CONFIGURED", message: "off" } }, { status: 503 }),
  ]);
  renderPanel();
  fireEvent.change(await screen.findByRole("textbox", { name: "Your question" }), { target: { value: "Sales?" } });
  fireEvent.click(screen.getByRole("button", { name: "Ask" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("You have asked many questions in the last hour.");
  fireEvent.click(screen.getByRole("button", { name: "Ask again" }));
  expect(await screen.findByText("The assistant is not switched on")).toBeInTheDocument();
});

test("model text is shown as text, never as markup", async () => {
  stubAssistant(CONFIGURED, [Response.json(reply({ answer: '<img src=x onerror="window.hacked=1"> <b>bold</b>', references: [], grounding: [] }))]);
  renderPanel();
  fireEvent.change(await screen.findByRole("textbox", { name: "Your question" }), { target: { value: "hi" } });
  fireEvent.click(screen.getByRole("button", { name: "Ask" }));
  expect(await screen.findByText(/<img src=x/)).toBeInTheDocument();
  expect(document.querySelector(".copilot-answer img, .copilot-answer b")).toBeNull();
});

test("the assistant speaks Arabic in an Arabic workspace and keeps each message's own direction", async () => {
  await i18n.changeLanguage("ar");
  stubAssistant(CONFIGURED, [Response.json(reply({ answer: "اتصل بـ Tyre Fresh Foods أولاً.", references: [], grounding: [{ tool: "get_daily_priorities", period: null, currency: "USD", ok: true }] }))]);
  renderPanel();
  fireEvent.click(await screen.findByRole("button", { name: "بمن يجب أن أتصل اليوم؟" }));
  const answer = await screen.findByText("اتصل بـ Tyre Fresh Foods أولاً.");
  expect(answer.closest("[dir]")).toHaveAttribute("dir", "auto");
  expect(screen.getByText("أولويات اليوم", { exact: false })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "مساعد الأعمال" })).toBeInTheDocument();
});
