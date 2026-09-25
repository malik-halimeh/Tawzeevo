import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import type { GroundedAnswer } from "../api/intelligence";
import { Icon } from "./Icon";
import { sectionHref } from "./workspaceSections";

/**
 * How every written answer reads, from the assistant or a contextual explanation (D-089/D-091):
 * the wording, then the customers it names (links to their records), what it was based on, and a
 * warning for any figure Tawzeevo did not supply. Model text is shown as text, never as markup.
 */

/** Plain text only: short paragraphs and list lines; markup characters are dropped, never rendered. */
export function AnswerText({ text, dir }: { text: string; dir: "rtl" | "ltr" }) {
  const blocks: { list: boolean; lines: string[] }[] = [];
  for (const raw of text.replace(/\*\*|__|`/g, "").split(/\r?\n/)) {
    let line = raw.trim().replace(/^#{1,6}\s+/, ""); // a heading reads as its words
    if (/^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?$/.test(line)) continue; // table rule line
    if (line.startsWith("|") && line.endsWith("|")) line = `- ${line.slice(1, -1).split("|").map((cell) => cell.trim()).filter(Boolean).join(" · ")}`; // table row → list line
    if (!line || line === "-") { blocks.push({ list: false, lines: [] }); continue; }
    const item = /^(?:[-*•]|\d{1,2}[.)])\s+(.*)$/.exec(line);
    const last = blocks[blocks.length - 1];
    if (item) {
      if (last?.list) last.lines.push(item[1]!); else blocks.push({ list: true, lines: [item[1]!] });
    } else if (last && !last.list && last.lines.length) last.lines.push(line);
    else blocks.push({ list: false, lines: [line] });
  }
  return (
    // The direction is the language the answer was written in, not its first letter, so an English
    // sentence that starts with an Arabic customer name still reads left to right.
    <div className="answer-text" dir={dir}>
      {blocks.filter((block) => block.lines.length).map((block, index) => block.list
        ? <ul key={index}>{block.lines.map((line, row) => <li key={row}>{line}</li>)}</ul>
        : <p key={index}>{block.lines.join(" ")}</p>)}
    </div>
  );
}

/** The customers named, the sources used and any flagged figure, under an answer. */
export function AnswerDetails({ response, tenantId }: { response: GroundedAnswer; tenantId: string }) {
  const { t } = useTranslation();
  const sources = response.grounding.filter((row) => row.ok);
  return (
    <>
      {response.references.length ? (
        <p className="copilot-meta"><span>{t("copilot.customersMentioned")}</span>
          {response.references.map((ref) => <Link className="chip-link" key={ref.ref} to={sectionHref("customers", tenantId, { customer: ref.customer_id })}>{ref.customer_name}</Link>)}
        </p>
      ) : null}
      {sources.length ? (
        <p className="copilot-meta copilot-sources"><Icon name="chart" small /><span>{t("copilot.basedOn")}</span>
          {sources.map((row, index) => (
            <span className="badge" key={`${row.tool}-${index}`}>
              {t(`copilot.tools.${row.tool}`, { defaultValue: row.tool })}
              {row.currency ? <> · <bdi dir="ltr">{row.currency}</bdi></> : null}
              {row.period ? <> · {t(`analytics.periods.${row.period}`, { defaultValue: row.period })}</> : null}
            </span>
          ))}
        </p>
      ) : null}
      {response.warnings.includes("UNVERIFIED_NUMBERS") ? (
        <p className="notice notice-warning" role="note">{t("copilot.unverified", { numbers: response.unverified_numbers.map((value) => `⁦${value}⁩`).join(", ") })}</p>
      ) : null}
      {response.warnings.includes("NO_TOOL_USED") ? <p className="notice notice-warning" role="note">{t("copilot.noTool")}</p> : null}
    </>
  );
}
