import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError } from "../api/client";
import { type ExplainContext, useCopilotStatus, useExplanation } from "../api/intelligence";
import { AnswerDetails, AnswerText } from "./AiAnswer";
import { Icon } from "./Icon";
import { ErrorState } from "./Ui";

/**
 * A written explanation where the owner already is (D-091): a customer's record, one unusual
 * change, the cash position. Nothing is written until the owner asks — one provider call per ask,
 * shared with the assistant's hourly limit — and the wording sits under the calculated figures it
 * explains, never instead of them. Parents key this by its context, so a different customer,
 * change, period or currency always starts unasked and never shows another context's summary.
 *
 * Without a configured assistant it says so in one line (or stays out of the way with
 * `whenOff="hide"`); a failure is shown inside it with a retry, and the page around it is unaffected.
 */
export function Explanation({ tenantId, context, label, whenOff = "note", onContextChanged }: {
  tenantId: string;
  context: ExplainContext;
  label: string;
  whenOff?: "note" | "hide";
  /** Called when the server says the explained item changed (e.g. the anomaly list moved on). */
  onContextChanged?: () => void;
}) {
  const { t, i18n } = useTranslation();
  const language = i18n.resolvedLanguage === "ar" ? "ar" : "en";
  const status = useCopilotStatus(tenantId);
  const [asked, setAsked] = useState(false);
  const explanation = useExplanation(tenantId, context, language, asked);
  const changed = explanation.error instanceof ApiError && explanation.error.code === "ANOMALY_CHANGED";
  useEffect(() => { if (changed) onContextChanged?.(); }, [changed, onContextChanged]);

  if (!status.data) return null; // the button appears once it is known whether it can work
  if (!status.data.configured) return whenOff === "hide" ? null : <p className="muted explain-off">{t("explain.off")}</p>;

  const shown = explanation.data;
  const writing = explanation.isFetching;
  // The first ask enables the query; later ones (or one over a summary kept from earlier) refetch.
  const ask = () => { if (asked || shown) void explanation.refetch(); else setAsked(true); };
  const time = shown ? new Date(shown.as_of).toLocaleTimeString(language === "ar" ? "ar-LB" : "en-GB", { hour: "2-digit", minute: "2-digit" }) : "";
  return (
    <div className="explanation" aria-live="polite">
      {!shown && !writing && !explanation.error ? <button className="text-btn explain-button" onClick={ask} type="button"><Icon name="chat" small />{label}</button> : null}
      {writing ? <p aria-busy="true" className="intel-pending muted"><span className="skeleton short" aria-hidden="true" />{t("explain.writing")}</p> : null}
      {explanation.error && !writing ? (
        <div className="intel-quiet-error">
          <ErrorState error={explanation.error} />
          {changed ? null : <button className="button button-secondary" onClick={ask} type="button"><Icon name="sync" small />{t("intelligence.retry")}</button>}
        </div>
      ) : null}
      {shown && !writing && !explanation.error ? (
        <div className="explain-card">
          <p className="explain-head"><Icon name="chat" small /><span>{t("explain.writtenAt", { time: `⁦${time}⁩` })}</span></p>
          <AnswerText dir={language === "ar" ? "rtl" : "ltr"} text={shown.answer} />
          <AnswerDetails response={shown} tenantId={tenantId} />
          <button className="text-btn explain-again" onClick={ask} type="button"><Icon name="sync" small />{t("explain.again")}</button>
        </div>
      ) : null}
    </div>
  );
}
