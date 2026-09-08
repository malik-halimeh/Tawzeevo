import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { apiBlobRequest, apiRequest } from "../api/client";
import type {
  BarcodeLookupResponse,
  Customer,
  CustomerBalancesResponse,
  CustomerDebtListResponse,
  CustomerObligationListResponse,
  CustomerPaymentResponse,
  CustomerSearchResponse,
  FinancialSettingsResponse,
  InvoiceCatalogMatch,
  InvoiceCatalogSearchResponse,
  InvoiceEditorResponse,
  InvoiceHistoryResponse,
  InvoiceItemParserResponse,
  ProductCostOption,
  ProductCostOptionsResponse,
  ProductPriceBasis,
  TenantProduct,
} from "../api/types";
import { ErrorState, SuccessNotice } from "./Ui";
import { InvoiceSharing } from "./InvoiceSharing";

interface AcceptedMatch {
  query: string;
  selected_product_id: string;
  score: string;
}

interface PendingFinancialIntent {
  scope: string;
  payload: Record<string, unknown>;
}

function financialIntent(
  pending: PendingFinancialIntent | null,
  scope: string,
  fields: Record<string, unknown>,
): PendingFinancialIntent {
  if (pending?.scope === scope) return pending;
  return {
    scope,
    payload: {
      idempotency_key: crypto.randomUUID(),
      ...fields,
      paid_at: new Date().toISOString(),
    },
  };
}

interface EditorLine {
  key: string;
  productId?: string | undefined;
  manualName?: string | undefined;
  name: string;
  imageUrl?: string | undefined;
  barcode?: string | undefined;
  quantity: string;
  basis: ProductPriceBasis;
  piecesPerBox?: number | undefined;
  manualUnitPrice?: string | undefined;
  lineDiscount: string;
  lineMarkup: string;
  acceptedMatch?: AcceptedMatch | undefined;
  costOptions: ProductCostOption[];
  supplierId?: string | undefined;
  costOverride: string;
  costOverrideReason: string;
}

function lineKey() {
  return crypto.randomUUID();
}

function money(value: string, currency: string) {
  return `${value} ${currency}`;
}

function productLine(
  match: InvoiceCatalogMatch,
  quantity = "1",
  acceptedMatch?: AcceptedMatch,
): EditorLine {
  const line: EditorLine = {
    key: lineKey(),
    productId: match.product_id,
    name: match.name,
    barcode: match.barcode,
    quantity,
    basis: match.package_level,
    lineDiscount: "0",
    lineMarkup: "0",
    acceptedMatch,
    costOptions: [],
    costOverride: "",
    costOverrideReason: "",
  };
  if (match.image_url) line.imageUrl = match.image_url;
  return line;
}

function scannedLine(product: TenantProduct, barcode: string, basis: ProductPriceBasis): EditorLine {
  const line: EditorLine = {
    key: lineKey(),
    productId: product.id,
    name: product.name,
    barcode,
    quantity: "1",
    basis,
    piecesPerBox: product.pieces_per_box ?? undefined,
    lineDiscount: "0",
    lineMarkup: "0",
    costOptions: [],
    costOverride: "",
    costOverrideReason: "",
  };
  if (product.images[0]) line.imageUrl = product.images[0].url;
  return line;
}

function InvoiceLineImage({ url, name }: { url: string; name: string }) {
  const [source, setSource] = useState<string>();

  useEffect(() => {
    let active = true;
    let objectUrl: string | undefined;
    void apiBlobRequest(url)
      .then((blob) => {
        if (!active) return;
        objectUrl = URL.createObjectURL(blob);
        setSource(objectUrl);
      })
      .catch(() => setSource(undefined));
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [url]);

  return source ? <img alt={name} className="invoice-line-image" src={source} /> : null;
}

export function InvoiceEditor({ tenantId }: { tenantId: string }) {
  const { t } = useTranslation();
  const [customerPhone, setCustomerPhone] = useState("");
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [customer, setCustomer] = useState<Customer>();
  const [currency, setCurrency] = useState("USD");
  const [barcode, setBarcode] = useState("");
  const [catalogQuery, setCatalogQuery] = useState("");
  const [catalogMatches, setCatalogMatches] = useState<InvoiceCatalogMatch[]>([]);
  const [textList, setTextList] = useState("");
  const [parsed, setParsed] = useState<InvoiceItemParserResponse>();
  const [manualName, setManualName] = useState("");
  const [manualPrice, setManualPrice] = useState("");
  const [manualQuantity, setManualQuantity] = useState("1");
  const [lines, setLines] = useState<EditorLine[]>([]);
  const [invoiceDiscount, setInvoiceDiscount] = useState("0");
  const [invoiceMarkup, setInvoiceMarkup] = useState("0");
  const [saved, setSaved] = useState<InvoiceEditorResponse>();
  const [history, setHistory] = useState<InvoiceHistoryResponse>();
  const [balances, setBalances] = useState<CustomerBalancesResponse>();
  const [debts, setDebts] = useState<CustomerDebtListResponse>({ debts: [] });
  const [overdueThreshold, setOverdueThreshold] = useState("");
  const [openingAmount, setOpeningAmount] = useState("");
  const [openingCurrency, setOpeningCurrency] = useState("USD");
  const [openingEffectiveAt, setOpeningEffectiveAt] = useState(
    new Date().toISOString().slice(0, 16),
  );
  const [obligations, setObligations] = useState<CustomerObligationListResponse>();
  const [allocationMode, setAllocationMode] = useState<"FIFO" | "OWNER">("FIFO");
  const [allocationAmounts, setAllocationAmounts] = useState<Record<string, string>>({});
  const [receiptAmount, setReceiptAmount] = useState("");
  const [receiptMethod, setReceiptMethod] = useState("CASH");
  const [receiptReference, setReceiptReference] = useState("");
  const [refundAmount, setRefundAmount] = useState("");
  const [refundMethod, setRefundMethod] = useState("CASH");
  const [reversalReason, setReversalReason] = useState("");
  const [cancelReason, setCancelReason] = useState("");
  const [lastPayment, setLastPayment] = useState<CustomerPaymentResponse>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [notice, setNotice] = useState<string>();
  const pendingReceipt = useRef<PendingFinancialIntent | null>(null);
  const pendingRefund = useRef<PendingFinancialIntent | null>(null);

  const run = async (operation: () => Promise<void>) => {
    setBusy(true);
    setError(undefined);
    setNotice(undefined);
    try {
      await operation();
    } catch (caught) {
      setError(caught);
    } finally {
      setBusy(false);
    }
  };

  const loadDebtDesk = useCallback(async () => {
    const [settings, debtList] = await Promise.all([
      apiRequest<FinancialSettingsResponse>(
        `/api/v1/customer-ledger/settings?tenant_id=${tenantId}`,
      ),
      apiRequest<CustomerDebtListResponse>(
        `/api/v1/customer-ledger/debts?tenant_id=${tenantId}`,
      ),
    ]);
    setOverdueThreshold(
      settings.customer_overdue_threshold_days === null
        ? ""
        : String(settings.customer_overdue_threshold_days),
    );
    setDebts(debtList);
  }, [tenantId]);

  const loadCustomerBalances = useCallback(async (customerId: string) => {
    setBalances(
      await apiRequest<CustomerBalancesResponse>(
        `/api/v1/customer-ledger/customers/${customerId}/balances?tenant_id=${tenantId}`,
      ),
    );
  }, [tenantId]);

  const loadHistory = useCallback(async (invoiceId: string) => {
    setHistory(
      await apiRequest<InvoiceHistoryResponse>(
        `/api/v1/invoices/${invoiceId}/history?tenant_id=${tenantId}`,
      ),
    );
  }, [tenantId]);

  const loadObligations = useCallback(async (customerId: string, selectedCurrency: string) => {
    setObligations(
      await apiRequest<CustomerObligationListResponse>(
        `/api/v1/payments/customers/${customerId}/obligations?tenant_id=${tenantId}` +
          `&currency=${selectedCurrency}`,
      ),
    );
  }, [tenantId]);

  useEffect(() => {
    void loadDebtDesk().catch(setError);
  }, [loadDebtDesk]);

  useEffect(() => {
    if (!customer) {
      setBalances(undefined);
      setObligations(undefined);
      return;
    }
    setOpeningCurrency(currency);
    void Promise.all([
      loadCustomerBalances(customer.id),
      loadObligations(customer.id, currency),
    ]).catch(setError);
  }, [customer, currency, loadCustomerBalances, loadObligations]);

  const changeLine = (key: string, changes: Partial<EditorLine>) => {
    setLines((current) => current.map((line) => (line.key === key ? { ...line, ...changes } : line)));
  };

  const loadCostOptions = async (line: EditorLine) => {
    if (!line.productId) return;
    const response = await apiRequest<ProductCostOptionsResponse>(
      `/api/v1/invoices/products/${line.productId}/cost-options?tenant_id=${tenantId}` +
        `&currency=${currency}&basis=${line.basis}`,
    );
    const preferred = response.options.find((option) => option.is_preferred);
    changeLine(line.key, {
      costOptions: response.options,
      supplierId: preferred?.supplier_id,
    });
  };

  const addLine = (line: EditorLine) => {
    setLines((current) => [...current, line]);
    void loadCostOptions(line).catch(setError);
  };

  const searchCustomers = (event: FormEvent) => {
    event.preventDefault();
    void run(async () => {
      const response = await apiRequest<CustomerSearchResponse>(
        `/api/v1/tenants/${tenantId}/customers/search?phone=${encodeURIComponent(customerPhone)}`,
      );
      setCustomers(response.customers);
      setNotice(t("invoiceEditor.customerMatches", { count: response.customers.length }));
    });
  };

  const scanBarcode = (event: FormEvent) => {
    event.preventDefault();
    void run(async () => {
      const result = await apiRequest<BarcodeLookupResponse>(
        `/api/v1/tenants/${tenantId}/catalog/barcodes/${encodeURIComponent(barcode)}`,
      );
      if (!result.tenant_product) {
        throw new Error(t("invoiceEditor.barcodeNotAdopted"));
      }
      addLine(scannedLine(result.tenant_product, result.barcode, result.package_level));
      setBarcode("");
      setNotice(t("invoiceEditor.itemAdded"));
    });
  };

  const searchCatalog = (event: FormEvent) => {
    event.preventDefault();
    void run(async () => {
      const result = await apiRequest<InvoiceCatalogSearchResponse>(
        `/api/v1/invoices/catalog-search?tenant_id=${tenantId}` +
          `&query=${encodeURIComponent(catalogQuery)}`,
      );
      setCatalogMatches(result.matches);
    });
  };

  const parseText = (event: FormEvent) => {
    event.preventDefault();
    void run(async () => {
      const result = await apiRequest<InvoiceItemParserResponse>(
        `/api/v1/invoices/item-parser?tenant_id=${tenantId}`,
        { method: "POST", body: JSON.stringify({ text: textList }) },
      );
      setParsed(result);
      for (const item of result.items) {
        if (item.resolution === "EXACT" && item.selected) {
          addLine(productLine(item.selected, item.quantity));
        }
      }
      setNotice(t("invoiceEditor.parserReady"));
    });
  };

  const acceptSuggestion = (query: string, quantity: string, match: InvoiceCatalogMatch) => {
    addLine(
      productLine(match, quantity, {
        query,
        selected_product_id: match.product_id,
        score: match.score,
      }),
    );
    setParsed((current) =>
      current
        ? {
            ...current,
            items: current.items.filter(
              (item) => !(item.normalized_query === query && item.quantity === quantity),
            ),
          }
        : undefined,
    );
  };

  const addManual = (event: FormEvent) => {
    event.preventDefault();
    addLine({
      key: lineKey(),
      manualName,
      name: manualName,
      quantity: manualQuantity,
      basis: "PIECE",
      manualUnitPrice: manualPrice,
      lineDiscount: "0",
      lineMarkup: "0",
      costOptions: [],
      costOverride: "",
      costOverrideReason: "",
    });
    setManualName("");
    setManualPrice("");
    setManualQuantity("1");
    setNotice(t("invoiceEditor.manualAdded"));
  };

  const saveDraft = () => {
    if (!customer) {
      setError(new Error(t("invoiceEditor.chooseCustomerFirst")));
      return;
    }
    if (!lines.length) {
      setError(new Error(t("invoiceEditor.addItemFirst")));
      return;
    }
    void run(async () => {
      const payload = {
        client_command_id: crypto.randomUUID(),
        expected_predecessor_revision_id: saved?.current_revision_id ?? null,
        customer_id: customer.id,
        currency,
        invoice_discount_expression: invoiceDiscount,
        invoice_markup_expression: invoiceMarkup,
        items: lines.map((line) => ({
          product_id: line.productId ?? null,
          manual_name: line.manualName ?? null,
          barcode: line.productId ? line.barcode ?? null : null,
          quantity_expression: line.quantity,
          price_basis: line.basis,
          pieces_per_box: line.piecesPerBox ?? null,
          manual_unit_price: line.manualUnitPrice || null,
          line_discount_expression: line.lineDiscount,
          line_markup_expression: line.lineMarkup,
          supplier_id: line.supplierId ?? null,
          cost_override: line.costOverride || null,
          cost_basis: line.costOverride ? line.basis : null,
          cost_pieces_per_box: line.costOverride ? line.piecesPerBox ?? null : null,
          cost_override_reason: line.costOverrideReason || null,
          accepted_fuzzy_match: line.acceptedMatch ?? null,
        })),
      };
      const result = await apiRequest<InvoiceEditorResponse>(
        saved
          ? `/api/v1/invoices/${saved.id}?tenant_id=${tenantId}`
          : `/api/v1/invoices?tenant_id=${tenantId}`,
        { method: saved ? "PUT" : "POST", body: JSON.stringify(payload) },
      );
      setSaved(result);
      await loadHistory(result.id);
      await Promise.all([
        loadDebtDesk(),
        loadCustomerBalances(result.customer_id),
        loadObligations(result.customer_id, result.currency),
      ]);
      setNotice(
        t(
          result.status === "CONFIRMED"
            ? "invoiceEditor.confirmedRevisionSaved"
            : saved
              ? "invoiceEditor.draftUpdated"
              : "invoiceEditor.draftCreated",
        ),
      );
    });
  };

  const confirmSaved = () => {
    if (!saved) return;
    void run(async () => {
      const confirmed = await apiRequest<InvoiceEditorResponse>(
        `/api/v1/invoices/${saved.id}/confirm?tenant_id=${tenantId}`,
        {
          method: "POST",
          body: JSON.stringify({ expected_revision_id: saved.current_revision_id }),
        },
      );
      setSaved(confirmed);
      await Promise.all([
        loadHistory(confirmed.id),
        loadDebtDesk(),
        loadCustomerBalances(confirmed.customer_id),
        loadObligations(confirmed.customer_id, confirmed.currency),
      ]);
      setNotice(t("invoiceEditor.invoiceConfirmed", { number: confirmed.official_invoice_number }));
    });
  };

  const saveOverdueThreshold = (event: FormEvent) => {
    event.preventDefault();
    void run(async () => {
      await apiRequest<FinancialSettingsResponse>(
        `/api/v1/customer-ledger/settings?tenant_id=${tenantId}`,
        {
          method: "PUT",
          body: JSON.stringify({
            customer_overdue_threshold_days:
              overdueThreshold === "" ? null : Number(overdueThreshold),
          }),
        },
      );
      await loadDebtDesk();
      setNotice(t("invoiceEditor.overdueThresholdSaved"));
    });
  };

  const recordOpeningBalance = (event: FormEvent) => {
    event.preventDefault();
    if (!customer) {
      setError(new Error(t("invoiceEditor.chooseCustomerFirst")));
      return;
    }
    void run(async () => {
      await apiRequest(
        `/api/v1/customer-ledger/opening-balances?tenant_id=${tenantId}`,
        {
          method: "POST",
          body: JSON.stringify({
            idempotency_key: crypto.randomUUID(),
            customer_id: customer.id,
            currency: openingCurrency,
            signed_amount: openingAmount,
            effective_at: new Date(openingEffectiveAt).toISOString(),
          }),
        },
      );
      setOpeningAmount("");
      await Promise.all([
        loadDebtDesk(),
        loadCustomerBalances(customer.id),
        loadObligations(customer.id, openingCurrency),
      ]);
      setNotice(t("invoiceEditor.openingBalanceSaved"));
    });
  };

  const recordReceipt = (event: FormEvent) => {
    event.preventDefault();
    if (!customer) {
      setError(new Error(t("invoiceEditor.chooseCustomerFirst")));
      return;
    }
    void run(async () => {
      const selectedAllocations =
        allocationMode === "OWNER"
          ? Object.entries(allocationAmounts)
              .filter(([, amount]) => Number(amount) > 0)
              .map(([target_ledger_entry_id, amount]) => ({
                target_ledger_entry_id,
                amount,
              }))
          : null;
      const command = financialIntent(
        pendingReceipt.current,
        `${tenantId}:${customer.id}:${currency}:CUSTOMER_RECEIPT`,
        {
          customer_id: customer.id,
          amount: receiptAmount,
          currency,
          method: receiptMethod || null,
          reference: receiptReference || null,
          allocations: selectedAllocations,
        },
      );
      pendingReceipt.current = command;
      const payment = await apiRequest<CustomerPaymentResponse>(
        `/api/v1/payments/customer-receipts?tenant_id=${tenantId}`,
        {
          method: "POST",
          body: JSON.stringify(command.payload),
        },
      );
      pendingReceipt.current = null;
      setLastPayment(payment);
      setReceiptAmount("");
      setReceiptReference("");
      setAllocationAmounts({});
      await Promise.all([
        loadCustomerBalances(customer.id),
        loadObligations(customer.id, currency),
        loadDebtDesk(),
      ]);
      setNotice(t("invoiceEditor.receiptRecorded"));
    });
  };

  const reverseLastReceipt = () => {
    if (!lastPayment || lastPayment.direction !== "CUSTOMER_RECEIPT") return;
    void run(async () => {
      const reversal = await apiRequest<CustomerPaymentResponse>(
        `/api/v1/payments/${lastPayment.id}/reverse?tenant_id=${tenantId}`,
        {
          method: "POST",
          body: JSON.stringify({
            idempotency_key: crypto.randomUUID(),
            reason: reversalReason,
          }),
        },
      );
      setLastPayment(reversal);
      setReversalReason("");
      if (customer) {
        await Promise.all([
          loadCustomerBalances(customer.id),
          loadObligations(customer.id, currency),
          loadDebtDesk(),
        ]);
      }
      setNotice(t("invoiceEditor.receiptReversed"));
    });
  };

  const recordRefund = (event: FormEvent) => {
    event.preventDefault();
    if (!customer) {
      setError(new Error(t("invoiceEditor.chooseCustomerFirst")));
      return;
    }
    void run(async () => {
      const command = financialIntent(
        pendingRefund.current,
        `${tenantId}:${customer.id}:${currency}:CUSTOMER_REFUND`,
        {
          customer_id: customer.id,
          amount: refundAmount,
          currency,
          method: refundMethod || null,
          reference: null,
        },
      );
      pendingRefund.current = command;
      const refund = await apiRequest<CustomerPaymentResponse>(
        `/api/v1/payments/customer-refunds?tenant_id=${tenantId}`,
        {
          method: "POST",
          body: JSON.stringify(command.payload),
        },
      );
      pendingRefund.current = null;
      setLastPayment(refund);
      setRefundAmount("");
      await Promise.all([
        loadCustomerBalances(customer.id),
        loadObligations(customer.id, currency),
        loadDebtDesk(),
      ]);
      setNotice(t("invoiceEditor.refundRecorded"));
    });
  };

  const cancelSaved = () => {
    if (!saved || saved.status === "CANCELLED") return;
    void run(async () => {
      const cancelled = await apiRequest<InvoiceEditorResponse>(
        `/api/v1/invoices/${saved.id}/cancel?tenant_id=${tenantId}`,
        {
          method: "POST",
          body: JSON.stringify({
            idempotency_key: crypto.randomUUID(),
            reason: cancelReason || null,
          }),
        },
      );
      setSaved(cancelled);
      setCancelReason("");
      await Promise.all([
        loadHistory(cancelled.id),
        loadDebtDesk(),
        loadCustomerBalances(cancelled.customer_id),
        loadObligations(cancelled.customer_id, cancelled.currency),
      ]);
      setNotice(t("invoiceEditor.invoiceCancelled"));
    });
  };

  return (
    <div className="invoice-editor" role="tabpanel">
      <header className="invoice-editor-heading">
        <div>
          <p className="section-kicker">{t("invoiceEditor.kicker")}</p>
          <h3>{t("invoiceEditor.title")}</h3>
          <p>{t("invoiceEditor.body")}</p>
        </div>
        <label className="field currency-field">
          <span>{t("tenantWorkspace.currency")}</span>
          <input
            disabled={saved?.status === "CONFIRMED" || saved?.status === "CANCELLED"}
            dir="ltr"
            maxLength={3}
            minLength={3}
            value={currency}
            onChange={(event) => setCurrency(event.target.value.toUpperCase())}
          />
        </label>
      </header>

      {error ? <ErrorState error={error} /> : null}
      {notice ? <SuccessNotice>{notice}</SuccessNotice> : null}

      <div className="invoice-editor-grid">
        <div className="invoice-entry-desk">
          <article className="content-card invoice-customer-card">
            <p className="section-kicker">{t("invoiceEditor.customerStep")}</p>
            <h4>{customer ? customer.name : t("invoiceEditor.findCustomer")}</h4>
            {customer ? (
              <div className="selected-customer">
                <div><bdi dir="ltr">{customer.phone}</bdi><span>{customer.address ?? "—"}</span></div>
                <span className="grade-seal">{customer.grade ?? "—"}</span>
                {!saved || saved.status === "DRAFT" ? <button className="text-button" onClick={() => setCustomer(undefined)} type="button">{t("common.change")}</button> : null}
              </div>
            ) : (
              <>
                <form className="inline-form" onSubmit={searchCustomers}>
                  <label className="field">
                    <span>{t("fields.phone")}</span>
                    <input dir="ltr" required value={customerPhone} onChange={(event) => setCustomerPhone(event.target.value)} />
                  </label>
                  <button className="button" disabled={busy} type="submit">{t("common.search")}</button>
                </form>
                <div className="invoice-customer-results">
                  {customers.map((match) => (
                    <button key={match.id} onClick={() => setCustomer(match)} type="button">
                      <strong>{match.name}</strong><bdi dir="ltr">{match.phone}</bdi><span>{match.address ?? "—"}</span>
                    </button>
                  ))}
                </div>
              </>
            )}
          </article>

          <article className="content-card item-entry-card">
            <p className="section-kicker">{t("invoiceEditor.itemStep")}</p>
            <h4>{t("invoiceEditor.addItems")}</h4>
            <div className="entry-methods">
              <form className="entry-method" onSubmit={scanBarcode}>
                <strong>{t("invoiceEditor.barcodeEntry")}</strong>
                <div className="inline-form"><input aria-label={t("tenantWorkspace.barcode")} dir="ltr" required value={barcode} onChange={(event) => setBarcode(event.target.value)} /><button className="button" disabled={busy} type="submit">{t("tenantWorkspace.scan")}</button></div>
              </form>
              <form className="entry-method" onSubmit={searchCatalog}>
                <strong>{t("invoiceEditor.catalogEntry")}</strong>
                <div className="inline-form"><input aria-label={t("invoiceEditor.catalogSearch")} required value={catalogQuery} onChange={(event) => setCatalogQuery(event.target.value)} /><button className="button button-secondary" disabled={busy} type="submit">{t("common.search")}</button></div>
                <div className="catalog-match-buttons">{catalogMatches.map((match) => <button key={match.product_id} onClick={() => addLine(productLine(match))} type="button"><strong>{match.name}</strong><span>{money(match.unit_price, match.currency)}</span></button>)}</div>
              </form>
              <form className="entry-method text-list-method" onSubmit={parseText}>
                <strong>{t("invoiceEditor.textEntry")}</strong>
                <textarea aria-label={t("invoiceEditor.textEntry")} placeholder={t("invoiceEditor.textPlaceholder")} required rows={4} value={textList} onChange={(event) => setTextList(event.target.value)} />
                <button className="button button-secondary" disabled={busy} type="submit">{t("invoiceEditor.parseList")}</button>
              </form>
              <form className="entry-method manual-entry-method" onSubmit={addManual}>
                <strong>{t("invoiceEditor.manualEntry")}</strong>
                <input placeholder={t("invoiceEditor.itemName")} required value={manualName} onChange={(event) => setManualName(event.target.value)} />
                <input aria-label={t("invoiceEditor.quantity")} dir="ltr" placeholder="1+1" required value={manualQuantity} onChange={(event) => setManualQuantity(event.target.value)} />
                <input aria-label={t("invoiceEditor.unitPrice")} dir="ltr" min="0" placeholder="0.0000" required step="0.0001" type="number" value={manualPrice} onChange={(event) => setManualPrice(event.target.value)} />
                <button className="button button-secondary" type="submit">{t("invoiceEditor.addManual")}</button>
              </form>
            </div>
            {parsed?.items.some((item) => item.resolution !== "EXACT") ? (
              <div className="match-confirmation" role="region" aria-label={t("invoiceEditor.confirmMatches")}>
                <strong>{t("invoiceEditor.confirmMatches")}</strong>
                {parsed.items.filter((item) => item.resolution !== "EXACT").map((item) => (
                  <div key={`${item.normalized_query}-${item.quantity}`}>
                    <span>{item.source_text}</span>
                    {item.suggestions.length ? item.suggestions.map((match) => (
                      <button key={match.product_id} onClick={() => acceptSuggestion(item.normalized_query, item.quantity, match)} type="button">{match.name} · {Math.round(Number(match.score) * 100)}%</button>
                    )) : <em>{t("invoiceEditor.noSafeMatch")}</em>}
                  </div>
                ))}
              </div>
            ) : null}
          </article>

          <section className="invoice-lines" aria-label={t("invoiceEditor.invoiceLines")}>
            {lines.map((line, index) => (
              <article className="invoice-line" key={line.key}>
                <span className="line-number">{String(index + 1).padStart(2, "0")}</span>
                <div className="line-main">{line.imageUrl ? <InvoiceLineImage name={line.name} url={line.imageUrl} /> : <span className="invoice-line-image invoice-line-image-empty" aria-hidden="true">□</span>}<span><strong>{line.name}</strong><code dir="ltr">{line.barcode ?? t("invoiceEditor.manual")}</code></span></div>
                <label className="field"><span>{t("invoiceEditor.quantityExpression")}</span><input dir="ltr" value={line.quantity} onChange={(event) => changeLine(line.key, { quantity: event.target.value })} /></label>
                <label className="field"><span>{t("tenantWorkspace.priceBasis")}</span><select value={line.basis} onChange={(event) => { const basis = event.target.value as ProductPriceBasis; changeLine(line.key, { basis, barcode: undefined }); void loadCostOptions({ ...line, basis, barcode: undefined }).catch(setError); }}><option value="PIECE">{t("tenantWorkspace.piece")}</option><option value="BOX">{t("tenantWorkspace.box")}</option></select></label>
                <label className="field"><span>{t("invoiceEditor.lineDiscount")}</span><input dir="ltr" value={line.lineDiscount} onChange={(event) => changeLine(line.key, { lineDiscount: event.target.value })} /></label>
                <label className="field"><span>{t("invoiceEditor.lineMarkup")}</span><input dir="ltr" value={line.lineMarkup} onChange={(event) => changeLine(line.key, { lineMarkup: event.target.value })} /></label>
                {line.costOptions.length ? <div className="line-cost-controls"><label className="field"><span>{t("invoiceEditor.supplierCost")}</span><select value={line.supplierId ?? ""} onChange={(event) => changeLine(line.key, { supplierId: event.target.value })}><option value="">—</option>{line.costOptions.map((option) => <option key={option.supplier_id} value={option.supplier_id}>{option.supplier_name} · {option.unit_cost ?? "—"} {option.currency}{option.is_preferred ? ` · ${t("invoiceEditor.preferred")}` : ""}</option>)}</select></label><label className="field"><span>{t("invoiceEditor.costOverride")}</span><input dir="ltr" min="0" step="0.0001" type="number" value={line.costOverride} onChange={(event) => changeLine(line.key, { costOverride: event.target.value })} /></label>{line.costOverride ? <label className="field field-wide"><span>{t("invoiceEditor.overrideReason")}</span><input required value={line.costOverrideReason} onChange={(event) => changeLine(line.key, { costOverrideReason: event.target.value })} /></label> : null}</div> : null}
                <button className="text-button danger-link remove-line" onClick={() => setLines((current) => current.filter((item) => item.key !== line.key))} type="button">{t("common.remove")}</button>
              </article>
            ))}
            {!lines.length ? <div className="invoice-empty-lines"><strong>{t("invoiceEditor.emptyTitle")}</strong><span>{t("invoiceEditor.emptyBody")}</span></div> : null}
          </section>
        </div>

        <aside className="invoice-tally" aria-label={t("invoiceEditor.totals")}>
          <div className="tally-top"><span>{t(saved?.status === "CONFIRMED" ? "invoiceEditor.confirmed" : saved?.status === "CANCELLED" ? "invoiceEditor.cancelled" : "invoiceEditor.draft")}</span><strong>{saved?.official_invoice_number ?? (saved ? `R${saved.server_revision_number}` : "R—")}</strong></div>
          <dl>
            <div><dt>{t("invoiceEditor.previousBalance")}</dt><dd dir="ltr">{saved ? money(saved.prior_balance, saved.currency) : "—"}</dd></div>
            <div><dt>{t("invoiceEditor.subtotal")}</dt><dd dir="ltr">{saved ? money(saved.subtotal, saved.currency) : "—"}</dd></div>
            <div><dt>{t("invoiceEditor.discounts")}</dt><dd dir="ltr">{saved ? `− ${money(saved.discount_total, saved.currency)}` : "—"}</dd></div>
            <div><dt>{t("invoiceEditor.markups")}</dt><dd dir="ltr">{saved ? `+ ${money(saved.markup_total, saved.currency)}` : "—"}</dd></div>
            <div className="net-sales"><dt>{t("invoiceEditor.netSales")}</dt><dd dir="ltr">{saved ? money(saved.net_sales, saved.currency) : "—"}</dd></div>
            <div className="total-due"><dt>{t("invoiceEditor.totalDue")}</dt><dd dir="ltr">{saved ? money(saved.total_due, saved.currency) : "—"}</dd></div>
          </dl>
          <div className="tally-adjustments"><label className="field"><span>{t("invoiceEditor.invoiceDiscount")}</span><input dir="ltr" value={invoiceDiscount} onChange={(event) => setInvoiceDiscount(event.target.value)} /></label><label className="field"><span>{t("invoiceEditor.invoiceMarkup")}</span><input dir="ltr" value={invoiceMarkup} onChange={(event) => setInvoiceMarkup(event.target.value)} /></label></div>
          {saved?.items.map((item) => <div className="saved-line-proof" key={item.id}>{item.media_snapshot.images?.[0]?.url ? <InvoiceLineImage name={item.product_name} url={item.media_snapshot.images[0].url} /> : null}<strong>{item.product_name}</strong><span>{item.price_source === "EXPLICIT_GRADE_PRICE" ? t("invoiceEditor.explicitGradePrice") : item.price_source === "GRADE_DISCOUNT" ? t("invoiceEditor.gradeDiscount", { value: item.grade_discount_percent }) : t("invoiceEditor.normalPrice")}</span><bdi dir="ltr">{money(item.line_total, saved.currency)}</bdi>{item.unit_cost ? <small>{t("invoiceEditor.costSnapshot", { value: item.unit_cost, currency: item.cost_currency })}</small> : null}</div>)}
          {saved?.status !== "CANCELLED" ? <button className="button tally-save" disabled={busy || !customer || !lines.length} onClick={saveDraft} type="button">{busy ? t("common.saving") : t(saved?.status === "CONFIRMED" ? "invoiceEditor.saveConfirmedRevision" : saved ? "invoiceEditor.recalculate" : "invoiceEditor.saveDraft")}</button> : null}
          {saved?.status === "DRAFT" ? <button className="button button-confirm" disabled={busy} onClick={confirmSaved} type="button">{t("invoiceEditor.confirmInvoice")}</button> : null}
          {saved && saved.status !== "CANCELLED" ? <div className="cancel-controls"><label className="field"><span>{t("invoiceEditor.cancellationReason")}</span><input value={cancelReason} onChange={(event) => setCancelReason(event.target.value)} /></label><button className="button button-danger" disabled={busy} onClick={cancelSaved} type="button">{t("invoiceEditor.cancelInvoice")}</button></div> : null}
          <p className="backend-note">{t("invoiceEditor.backendNote")}</p>
          {history?.revisions.length ? <section className="invoice-history" aria-label={t("invoiceEditor.revisionHistory")}><h4>{t("invoiceEditor.revisionHistory")}</h4>{history.revisions.map((revision) => <article className={revision.is_current ? "is-current" : ""} key={revision.current_revision_id}><div><strong>R{revision.server_revision_number}</strong>{revision.is_current ? <span>{t("invoiceEditor.currentRevision")}</span> : null}</div><time dateTime={revision.revision_created_at}>{new Date(revision.revision_created_at).toLocaleString()}</time><bdi dir="ltr">{money(revision.net_sales, revision.currency)}</bdi>{revision.ledger_delta !== null ? <small dir="ltr">Δ {money(revision.ledger_delta, revision.currency)}</small> : null}</article>)}</section> : null}
        </aside>
      </div>
      {saved ? <InvoiceSharing key={saved.id} tenantId={tenantId} invoiceId={saved.id} /> : null}

      <section className="settlement-desk" aria-labelledby="settlement-desk-title">
        <header>
          <div><p className="section-kicker">{t("invoiceEditor.settlementKicker")}</p><h3 id="settlement-desk-title">{t("invoiceEditor.settlementTitle")}</h3><p>{t("invoiceEditor.settlementBody")}</p></div>
          {customer ? <div className="settlement-customer"><strong>{customer.name}</strong><bdi dir="ltr">{currency}</bdi></div> : <span>{t("invoiceEditor.chooseCustomerFirst")}</span>}
        </header>
        <div className="settlement-grid">
          <article className="content-card obligation-card">
            <div className="settlement-card-heading"><div><span>01</span><h4>{t("invoiceEditor.openObligations")}</h4></div><div className="allocation-mode" role="group" aria-label={t("invoiceEditor.allocationMode")}><button aria-pressed={allocationMode === "FIFO"} onClick={() => setAllocationMode("FIFO")} type="button">{t("invoiceEditor.fifoAllocation")}</button><button aria-pressed={allocationMode === "OWNER"} onClick={() => setAllocationMode("OWNER")} type="button">{t("invoiceEditor.ownerAllocation")}</button></div></div>
            {obligations?.obligations.length ? <div className="obligation-list">{obligations.obligations.map((obligation) => <label className="obligation-row" key={obligation.target_ledger_entry_id}><span><strong>{obligation.label}</strong><time dateTime={obligation.effective_at}>{new Date(obligation.effective_at).toLocaleDateString()}</time></span><bdi dir="ltr">{money(obligation.outstanding_amount, currency)}</bdi>{allocationMode === "OWNER" ? <input aria-label={t("invoiceEditor.allocateTo", { label: obligation.label })} dir="ltr" max={obligation.outstanding_amount} min="0" placeholder="0.0000" step="0.0001" type="number" value={allocationAmounts[obligation.target_ledger_entry_id] ?? ""} onChange={(event) => setAllocationAmounts((current) => ({ ...current, [obligation.target_ledger_entry_id]: event.target.value }))} /> : <span className="fifo-mark">{t("invoiceEditor.fifoQueued")}</span>}</label>)}</div> : <p className="empty-copy">{t("invoiceEditor.noOpenObligations")}</p>}
          </article>
          <form className="content-card receipt-card" onSubmit={recordReceipt}>
            <div className="settlement-card-heading"><div><span>02</span><h4>{t("invoiceEditor.recordReceipt")}</h4></div></div>
            <label className="field"><span>{t("invoiceEditor.receiptAmount")}</span><input dir="ltr" min="0.0001" required step="0.0001" type="number" value={receiptAmount} onChange={(event) => setReceiptAmount(event.target.value)} /></label>
            <label className="field"><span>{t("invoiceEditor.paymentMethod")}</span><input value={receiptMethod} onChange={(event) => setReceiptMethod(event.target.value)} /></label>
            <label className="field"><span>{t("invoiceEditor.paymentReference")}</span><input value={receiptReference} onChange={(event) => setReceiptReference(event.target.value)} /></label>
            <button className="button" disabled={busy || !customer} type="submit">{t("invoiceEditor.recordReceipt")}</button>
          </form>
          <form className="content-card refund-card" onSubmit={recordRefund}>
            <div className="settlement-card-heading"><div><span>03</span><h4>{t("invoiceEditor.issueRefund")}</h4></div></div>
            <p>{t("invoiceEditor.refundCeilingBody")}</p>
            <label className="field"><span>{t("invoiceEditor.refundAmount")}</span><input dir="ltr" min="0.0001" required step="0.0001" type="number" value={refundAmount} onChange={(event) => setRefundAmount(event.target.value)} /></label>
            <label className="field"><span>{t("invoiceEditor.paymentMethod")}</span><input value={refundMethod} onChange={(event) => setRefundMethod(event.target.value)} /></label>
            <button className="button button-secondary" disabled={busy || !customer} type="submit">{t("invoiceEditor.issueRefund")}</button>
          </form>
        </div>
        {lastPayment ? <article className="payment-slip" aria-live="polite"><div><span>{t(`invoiceEditor.paymentDirection.${lastPayment.direction}`)}</span><strong dir="ltr">{money(lastPayment.amount, lastPayment.currency)}</strong></div><dl><div><dt>{t("invoiceEditor.allocated")}</dt><dd dir="ltr">{money(lastPayment.allocated_amount, lastPayment.currency)}</dd></div><div><dt>{t("invoiceEditor.unallocatedCredit")}</dt><dd dir="ltr">{money(lastPayment.unallocated_amount, lastPayment.currency)}</dd></div><div><dt>{t("invoiceEditor.customerBalance")}</dt><dd dir="ltr">{money(lastPayment.customer_balance, lastPayment.currency)}</dd></div><div><dt>{t("invoiceEditor.availableCredit")}</dt><dd dir="ltr">{money(lastPayment.available_credit, lastPayment.currency)}</dd></div></dl>{lastPayment.direction === "CUSTOMER_RECEIPT" ? <div className="receipt-reversal"><label className="field"><span>{t("invoiceEditor.reversalReason")}</span><input required value={reversalReason} onChange={(event) => setReversalReason(event.target.value)} /></label><button className="text-button danger-link" disabled={busy || !reversalReason.trim()} onClick={reverseLastReceipt} type="button">{t("invoiceEditor.reverseReceipt")}</button></div> : null}</article> : null}
      </section>
      <section className="debt-desk" aria-labelledby="debt-desk-title">
        <header><div><p className="section-kicker">{t("invoiceEditor.debtKicker")}</p><h3 id="debt-desk-title">{t("invoiceEditor.debtTitle")}</h3></div><form className="threshold-form" onSubmit={saveOverdueThreshold}><label className="field"><span>{t("invoiceEditor.overdueThreshold")}</span><input dir="ltr" min="0" type="number" value={overdueThreshold} onChange={(event) => setOverdueThreshold(event.target.value)} /></label><button className="button button-secondary" disabled={busy} type="submit">{t("common.saveChanges")}</button></form></header>
        <div className="debt-desk-grid">
          <article className="content-card opening-balance-card"><h4>{t("invoiceEditor.openingBalance")}</h4><p>{t("invoiceEditor.openingBalanceBody")}</p>{customer ? <><strong>{customer.name}</strong><div className="balance-chips">{balances?.balances.length ? balances.balances.map((balance) => <span dir="ltr" key={balance.currency}>{money(balance.balance, balance.currency)}</span>) : <span>{t("invoiceEditor.noLedgerBalance")}</span>}</div></> : null}<form className="form-grid" onSubmit={recordOpeningBalance}><label className="field"><span>{t("invoiceEditor.signedOpeningAmount")}</span><input dir="ltr" required step="0.0001" type="number" value={openingAmount} onChange={(event) => setOpeningAmount(event.target.value)} /></label><label className="field"><span>{t("tenantWorkspace.currency")}</span><input dir="ltr" maxLength={3} minLength={3} required value={openingCurrency} onChange={(event) => setOpeningCurrency(event.target.value.toUpperCase())} /></label><label className="field field-wide"><span>{t("invoiceEditor.effectiveAt")}</span><input required type="datetime-local" value={openingEffectiveAt} onChange={(event) => setOpeningEffectiveAt(event.target.value)} /></label><button className="button field-wide" disabled={busy || !customer} type="submit">{t("invoiceEditor.recordOpeningBalance")}</button></form></article>
          <article className="content-card debt-register"><h4>{t("invoiceEditor.customerDebt")}</h4>{debts.debts.length ? debts.debts.map((debt) => <div className={debt.is_overdue ? "debt-row is-overdue" : "debt-row"} key={`${debt.customer_id}-${debt.currency}`}><span className="debt-alert-mark" aria-hidden="true">{debt.is_overdue ? "!" : "·"}</span><div><strong>{debt.customer_name}</strong><bdi dir="ltr">{debt.customer_phone}</bdi></div><bdi className="debt-amount" dir="ltr">{money(debt.balance, debt.currency)}</bdi><span>{debt.is_overdue ? t("invoiceEditor.overdueBy", { days: debt.overdue_age_days }) : t("invoiceEditor.currentDebt")}</span></div>) : <p className="empty-copy">{t("invoiceEditor.noCustomerDebt")}</p>}</article>
        </div>
      </section>
    </div>
  );
}
