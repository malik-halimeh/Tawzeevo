import { type KeyboardEvent, type ReactNode, useEffect, useId, useRef, useState } from "react";
import { Trans, useTranslation } from "react-i18next";

import "../../listKit.css";
import { Icon } from "../Icon";
import { PageHeader } from "../Ui";

export const SEARCH_DELAY_MS = 250;

/**
 * A list page's title line: title, optional count with the sort control beside it, an optional
 * search button that opens an inline search field, and optional page actions.
 *
 * `onSearch` receives the text 250 ms after typing stops, and at once when the field is cleared or
 * closed (closing always clears it so the list never stays narrowed by text the owner cannot see).
 * `countKey` is an i18n plural key whose strings may wrap the number in `<n></n>`.
 */
export function ListHeader({ title, eyebrow, count, countKey = "listKit.count", sort, onSearch, searchLabel, defaultSearch = "", actions }: {
  title: string;
  eyebrow?: string;
  count?: number | undefined;
  countKey?: string;
  sort?: ReactNode;
  onSearch?: (text: string) => void;
  searchLabel?: string;
  defaultSearch?: string;
  actions?: ReactNode;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(defaultSearch !== "");
  const [text, setText] = useState(defaultSearch);
  const toggle = useRef<HTMLButtonElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const sent = useRef(defaultSearch);
  const latest = useRef(onSearch);
  const focusField = useRef(false);
  const fieldId = useId();
  useEffect(() => { latest.current = onSearch; });
  useEffect(() => () => clearTimeout(timer.current), []);
  useEffect(() => {
    if (open && focusField.current) input.current?.focus();
    focusField.current = false;
  }, [open]);

  function send(value: string) {
    clearTimeout(timer.current);
    if (value === sent.current) return;
    sent.current = value;
    latest.current?.(value);
  }

  function type(value: string) {
    setText(value);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => send(value), SEARCH_DELAY_MS);
  }

  function clear() {
    setText("");
    send("");
    input.current?.focus();
  }

  function close() {
    setText("");
    send("");
    setOpen(false);
    toggle.current?.focus();
  }

  function onFieldKey(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Escape") { event.preventDefault(); close(); }
  }

  const label = searchLabel ?? t("listKit.searchLabel");
  const searchButton = onSearch ? (
    <button
      aria-controls={open ? fieldId : undefined}
      aria-expanded={open}
      aria-label={t("common.search")}
      className="list-icon-button"
      onClick={() => { if (open) { close(); return; } focusField.current = true; setOpen(true); }}
      ref={toggle}
      type="button"
    >
      <Icon name="search" />
    </button>
  ) : null;
  const tools = searchButton || actions ? <>{searchButton}{actions}</> : null;

  return (
    <PageHeader actions={tools} className="list-head" eyebrow={eyebrow} title={title}>
      {open ? (
        <div className="list-search" id={fieldId} role="search">
          <label className="sr-only" htmlFor={`${fieldId}-input`}>{label}</label>
          <Icon name="search" small />
          <input
            autoComplete="off"
            enterKeyHint="search"
            id={`${fieldId}-input`}
            onChange={(event) => type(event.target.value)}
            onKeyDown={onFieldKey}
            ref={input}
            type="search"
            value={text}
          />
          {text ? (
            <button aria-label={t("listKit.clearSearch")} className="list-search-clear" onClick={clear} type="button"><Icon name="close" small /></button>
          ) : null}
        </div>
      ) : null}
      {count !== undefined || sort ? (
        <div className="list-head-meta">
          {count !== undefined ? <p className="list-head-count"><Trans components={{ n: <bdi dir="ltr" /> }} count={count} i18nKey={countKey} /></p> : null}
          {sort}
        </div>
      ) : null}
    </PageHeader>
  );
}
