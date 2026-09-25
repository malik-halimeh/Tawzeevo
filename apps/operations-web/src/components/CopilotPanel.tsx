import { type FormEvent, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { ApiError } from "../api/client";
import { askCopilot, type CopilotResponse, type CopilotTurn, useCopilotStatus } from "../api/intelligence";
import { AnswerDetails, AnswerText } from "./AiAnswer";
import { Icon } from "./Icon";
import { ErrorState, LoadingState } from "./Ui";
import { sectionHref } from "./workspaceSections";

/**
 * Business assistant (D-089): the owner asks in their own words and gets an answer written from
 * the same deterministic figures Customers and Analytics show. It is read-only — it cannot
 * record, edit or delete anything — and the server stores no conversation: this screen keeps the
 * history and sends it back with each question (the answers' reference form, never names).
 * Without a configured provider the section says so plainly; every other screen keeps working.
 */
interface Turn { question: string; response?: CopilotResponse; error?: unknown }

const MAX_HISTORY_TURNS = 6; // the API accepts 12 messages: six questions and their answers
const SUGGESTIONS = ["callToday", "overdue", "unusual", "collected"] as const;

/** Arabic script in the question means an Arabic answer (the assistant answers in the question's language). */
const questionDirection = (question: string) => (/[\u0600-\u06ff]/.test(question) ? "rtl" : "ltr");

function Answer({ response, question, tenantId }: { response: CopilotResponse; question: string; tenantId: string }) {
  return (
    <div className="copilot-answer">
      <AnswerText dir={questionDirection(question)} text={response.answer} />
      <AnswerDetails response={response} tenantId={tenantId} />
    </div>
  );
}

function SetupRequired({ tenantId }: { tenantId: string }) {
  const { t } = useTranslation();
  return (
    <div className="empty-state copilot-setup">
      <Icon name="chat" />
      <strong>{t("copilot.setupTitle")}</strong>
      <p>{t("copilot.setupBody")}</p>
      <p className="copilot-setup-links">
        <Link to={sectionHref("customers", tenantId)}>{t("copilot.goPriorities")}</Link>
        <Link to={sectionHref("analytics", tenantId)}>{t("copilot.goAnalytics")}</Link>
      </p>
    </div>
  );
}

export function CopilotPanel({ tenantId }: { tenantId: string }) {
  const { t } = useTranslation();
  const status = useCopilotStatus(tenantId);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [unconfigured, setUnconfigured] = useState(false);
  const input = useRef<HTMLTextAreaElement>(null);

  const answered = turns.filter((turn) => turn.response);
  const conversationId = answered[answered.length - 1]?.response?.conversation_id ?? null;

  const send = (question: string, previous: Turn[]) => {
    const history: CopilotTurn[] = previous.filter((turn) => turn.response).slice(-MAX_HISTORY_TURNS).flatMap((turn) => [
      { role: "user" as const, content: turn.question },
      { role: "assistant" as const, content: turn.response!.conversation_text },
    ]);
    setBusy(true);
    setTurns([...previous, { question }]);
    askCopilot(tenantId, question, history, conversationId)
      .then((response) => setTurns([...previous, { question, response }]))
      .catch((error: unknown) => {
        if (error instanceof ApiError && error.code === "COPILOT_NOT_CONFIGURED") { setUnconfigured(true); void status.refetch(); }
        setTurns([...previous, { question, error }]);
      })
      .finally(() => { setBusy(false); input.current?.focus(); });
  };
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const question = draft.trim();
    if (!question || busy) return;
    setDraft("");
    send(question, turns);
  };
  // Asking again is safe: the assistant only reads, so a retried question changes nothing.
  const retry = () => {
    const last = turns[turns.length - 1];
    if (last) send(last.question, turns.slice(0, -1));
  };
  const reset = () => { setTurns([]); setDraft(""); input.current?.focus(); };

  const configured = status.data?.configured === true && !unconfigured;
  return (
    <section aria-labelledby="copilot-title" className="copilot">
      <header className="section-head">
        <p className="eyebrow"><Icon name="chat" small />{t("copilot.kicker")}</p>
        <h3 id="copilot-title">{t("copilot.title")}</h3>
        <p>{t("copilot.body")}</p>
      </header>
      {status.isPending ? <LoadingState /> : null}
      {status.error ? <><ErrorState error={status.error} /><button className="button button-secondary" onClick={() => { void status.refetch(); }} type="button"><Icon name="sync" small />{t("intelligence.retry")}</button></> : null}
      {status.data && !configured ? <SetupRequired tenantId={tenantId} /> : null}
      {configured ? (
        <>
          {turns.length ? (
            <ol aria-label={t("copilot.conversation")} aria-live="polite" className="copilot-thread">
              {turns.map((turn, index) => (
                <li key={index}>
                  <p className="copilot-question" dir="auto"><span className="sr-only">{t("copilot.you")}: </span>{turn.question}</p>
                  {turn.response ? <Answer question={turn.question} response={turn.response} tenantId={tenantId} /> : null}
                  {turn.error ? (
                    <div className="copilot-error">
                      <ErrorState error={turn.error} />
                      {index === turns.length - 1 && !unconfigured ? <button className="button button-secondary" disabled={busy} onClick={retry} type="button"><Icon name="sync" small />{t("copilot.askAgain")}</button> : null}
                    </div>
                  ) : null}
                  {!turn.response && !turn.error ? <p className="muted copilot-thinking" role="status">{t("copilot.thinking")}</p> : null}
                </li>
              ))}
            </ol>
          ) : (
            <div className="copilot-suggestions">
              <p className="muted">{t("copilot.tryAsking")}</p>
              <div className="chips">{SUGGESTIONS.map((key) => <button className="text-button" disabled={busy} key={key} onClick={() => send(t(`copilot.suggestions.${key}`), turns)} type="button">{t(`copilot.suggestions.${key}`)}</button>)}</div>
            </div>
          )}
          <form className="copilot-form" onSubmit={submit}>
            <label className="field field-wide"><span>{t("copilot.question")}</span>
              <textarea dir="auto" maxLength={1000} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) submit(event); }} ref={input} rows={2} value={draft} />
            </label>
            <div className="form-actions">
              <button className="button" disabled={busy || !draft.trim()} type="submit">{busy ? t("copilot.thinkingShort") : t("copilot.ask")}</button>
              {turns.length ? <button className="button button-secondary" disabled={busy} onClick={reset} type="button">{t("copilot.newConversation")}</button> : null}
            </div>
          </form>
          <p className="work-footnote"><Icon name="shield" small />{t("copilot.privacy")}</p>
        </>
      ) : null}
    </section>
  );
}
