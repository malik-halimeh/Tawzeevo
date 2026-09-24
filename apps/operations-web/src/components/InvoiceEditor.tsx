import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { apiBlobRequest, apiRequest } from "../api/client";
import { financialIntent, retireFinancialIntent } from "../api/financialIntent";
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
  InvoiceEditorItem,
  InvoiceEditorResponse,
  InvoiceHistoryResponse,
  InvoiceItemParserResponse,
  ProductCostOption,
  ProductCostOptionsResponse,
  ProductPriceBasis,
  TenantProduct,
} from "../api/types";
import { Link } from "react-router-dom";

import { Arrow } from "./Icon";
import { ErrorState, SuccessNotice } from "./Ui";
import { InvoiceSharing } from "./InvoiceSharing";
import { NextSteps } from "./NextSteps";
import { sectionHref } from "./workspaceSections";
import type { Supplier } from "./SupplierSetup";
import { queueInvoiceConfirm, queueInvoiceDraft, queueInvoiceUpdate, queueReceipt } from "../offline/commands";
import { browserOffline } from "../offline/network";
import { findLocalProductByBarcode, searchLocalCustomers } from "../offline/sync";

interface AcceptedMatch {
  query: string;
  selected_product_id: string;
  score: string;
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

/**
 * Presentation groupings of the one Invoices section (docs/design-references/DESIGN_DIRECTION.md;
 * review-artifacts direction for slice 2): distinct views for the invoice itself, payments and
 * balances, and one visible item-entry method at a time. They choose what is shown, never what is sent.
 */
type InvoiceView = "invoice" | "payments" | "balances";
type EntryMethod = "barcode" | "catalog" | "text" | "manual";
const INVOICE_VIEWS: readonly (readonly [InvoiceView, string])[] = [
  ["invoice", "invoiceEditor.viewInvoice"],
  ["payments", "invoiceEditor.viewPayments"],
  ["balances", "invoiceEditor.viewBalances"],
];
const ENTRY_METHODS: readonly (readonly [EntryMethod, string])[] = [
  ["barcode", "invoiceEditor.barcodeEntry"],
  ["catalog", "invoiceEditor.catalogEntry"],
  ["text", "invoiceEditor.textEntry"],
  ["manual", "invoiceEditor.manualEntry"],
];

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

export function InvoiceEditor({ tenantId, membershipId, onOpenSupplierSetup, invoiceId = null, initialView = null }: { tenantId: string; membershipId: string; onOpenSupplierSetup?: () => void; invoiceId?: string | null; initialView?: string | null }) {
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
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  // D-045: one create command per unsaved invoice. It survives failed attempts and is only replaced
  // once the server has acknowledged the header, so a retry can never create a second draft.
  const createCommandRef = useRef<string | undefined>(undefined);
  const [notice, setNotice] = useState<string>();
  const mounted = useRef(false);
  // Presentation state only: the open view, the visible item-entry method and whether a confirmed
  // invoice is open in the revision editor. Every view stays mounted, so inputs survive switching.
  const [view, setView] = useState<InvoiceView>("invoice");
  // An official invoice opened from a link (order next steps, a delivery, a payment line) is shown
  // read-only: nothing that depends on editor lines is offered, because they were never loaded.
  const [openedByLink, setOpenedByLink] = useState(false);
  // Entering payments for one invoice selects its open amount through the existing "choose amounts"
  // allocation; the receipt command and its rules are the same as when the owner picks it by hand.
  const [paymentFor, setPaymentFor] = useState<{ id: string; number: string | null; applied: boolean } | null>(null);
  const [entryMethod, setEntryMethod] = useState<EntryMethod>("barcode");
  const [revising, setRevising] = useState(false);
  const customerPhoneInput = useRef<HTMLInputElement>(null);
  const documentTitle = useRef<HTMLHeadingElement>(null);
  const revisionTitle = useRef<HTMLParagraphElement>(null);
  const revisingNow = useRef(false);
  const focusDocumentTitle = useRef(false);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  // A saved revision or a cancellation ends the revision editor: the document shows the new state and
  // takes focus once it is on screen, because the button that was used is no longer there.
  useEffect(() => { revisingNow.current = revising; }, [revising]);
  useEffect(() => {
    if (!revisingNow.current) return;
    focusDocumentTitle.current = true;
    setRevising(false);
  }, [saved?.current_revision_id, saved?.status]);
  useEffect(() => {
    if (!focusDocumentTitle.current || !documentTitle.current) return;
    focusDocumentTitle.current = false;
    documentTitle.current.focus();
  });

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

  // Opened from a link: load that official invoice with its customer and currency. A draft, an
  // unknown invoice or another business's invoice is ignored and the editor stays as it is.
  useEffect(() => {
    if (!invoiceId) return;
    let live = true;
    void (async () => {
      try {
        const loaded = await apiRequest<InvoiceEditorResponse>(`/api/v1/invoices/${invoiceId}?tenant_id=${tenantId}`);
        if (!live || (loaded.status !== "CONFIRMED" && loaded.status !== "CANCELLED")) return;
        const owner = await apiRequest<Customer>(`/api/v1/tenants/${tenantId}/customers/${loaded.customer_id}?tenant_id=${tenantId}`);
        if (!live) return;
        setOpenedByLink(true);
        setSaved(loaded);
        setCurrency(loaded.currency);
        setCustomer(owner);
        if (initialView === "payments" && loaded.status === "CONFIRMED") {
          setPaymentFor({ id: loaded.id, number: loaded.official_invoice_number, applied: false });
          setView("payments");
        }
        await loadHistory(loaded.id);
      } catch {
        // Not this business's invoice, or no longer available: nothing is selected.
      }
    })();
    return () => { live = false; };
  }, [invoiceId, initialView, tenantId, loadHistory]);

  // Once the customer's open obligations are on screen, select this invoice's open amount once.
  useEffect(() => {
    if (!paymentFor || paymentFor.applied || !obligations) return;
    const row = obligations.obligations.find((obligation) => obligation.source_type === "INVOICE" && obligation.source_id === paymentFor.id);
    setPaymentFor({ ...paymentFor, applied: true });
    if (!row) return;
    setAllocationMode("OWNER");
    setAllocationAmounts({ [row.target_ledger_entry_id]: row.outstanding_amount });
    setReceiptAmount(row.outstanding_amount);
  }, [obligations, paymentFor]);

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

  useEffect(() => {
    apiRequest<{ suppliers: Supplier[] }>(`/api/v1/suppliers?tenant_id=${tenantId}`)
      .then((response) => setSuppliers(response.suppliers))
      .catch(() => setSuppliers([]));
  }, [tenantId]);

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
      try {
        const response = await apiRequest<CustomerSearchResponse>(
          `/api/v1/tenants/${tenantId}/customers/search?phone=${encodeURIComponent(customerPhone)}`,
        );
        setCustomers(response.customers);
        setNotice(t("invoiceEditor.customerMatches", { count: response.customers.length }));
      } catch (problem) {
        // Network failure (offline): fall back to the local projection downloaded for this device.
        if (!(problem instanceof TypeError)) throw problem;
        const local = await searchLocalCustomers(tenantId, membershipId, customerPhone);
        setCustomers(local.map((row) => ({ ...row, phone_raw: row.phone_raw ?? row.phone, latitude: row.latitude, longitude: row.longitude, grade: row.grade })) as unknown as Customer[]);
        setNotice(t("invoiceEditor.offlineMatches", { count: local.length }));
      }
    });
  };

  const scanBarcode = (event: FormEvent) => {
    event.preventDefault();
    void run(async () => {
      let result: BarcodeLookupResponse;
      try {
        result = await apiRequest<BarcodeLookupResponse>(
          `/api/v1/tenants/${tenantId}/catalog/barcodes/${encodeURIComponent(barcode)}`,
        );
      } catch (problem) {
        // Offline: the local catalog projection answers; the server still prices the line on save.
        if (!(problem instanceof TypeError)) throw problem;
        const local = await findLocalProductByBarcode(tenantId, membershipId, barcode);
        if (!local) throw new Error(t("invoiceEditor.barcodeNotAdopted"));
        addLine(scannedLine({ ...local.product, images: [] } as unknown as TenantProduct, local.barcode.barcode, local.barcode.package_level));
        setBarcode("");
        setNotice(t("invoiceEditor.itemAddedOffline"));
        return;
      }
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
      if (!saved && !createCommandRef.current) createCommandRef.current = crypto.randomUUID();
      const payload = {
        client_command_id: saved ? crypto.randomUUID() : createCommandRef.current,
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
      let result: InvoiceEditorResponse;
      try {
        result = await apiRequest<InvoiceEditorResponse>(
          saved
            ? `/api/v1/invoices/${saved.id}?tenant_id=${tenantId}`
            : `/api/v1/invoices?tenant_id=${tenantId}`,
          { method: saved ? "PUT" : "POST", body: JSON.stringify(payload) },
        );
      } catch (problem) {
        // Offline: keep the exact request on this device; it is sent once when the connection returns.
        if (!(problem instanceof TypeError) || !browserOffline()) throw problem;
        if (saved) {
          // Offline edit of a known invoice: the predecessor revision travels with the command.
          try {
            await queueInvoiceUpdate(tenantId, membershipId, saved.id, {
              customer_id: payload.customer_id,
              currency: payload.currency,
              invoice_discount_expression: payload.invoice_discount_expression,
              invoice_markup_expression: payload.invoice_markup_expression,
              items: payload.items,
              expected_predecessor_revision_id: saved.current_revision_id,
              confirmed: saved.status === "CONFIRMED",
            });
          } catch {
            throw problem;
          }
          setNotice(t("invoiceEditor.updateQueuedOffline"));
          return;
        }
        let local;
        try {
          local = await queueInvoiceDraft(tenantId, membershipId, {
            customer_id: payload.customer_id,
            currency: payload.currency,
            invoice_discount_expression: payload.invoice_discount_expression,
            invoice_markup_expression: payload.invoice_markup_expression,
            items: payload.items,
            client_command_id: payload.client_command_id ?? null,
          });
        } catch {
          throw problem; // no local queue available: keep the stable command (D-045) for a manual retry
        }
        createCommandRef.current = undefined;
        setNotice(t("invoiceEditor.queuedOffline", { reference: local.pending_reference ?? "" }));
        return;
      }
      setSaved(result);
      createCommandRef.current = undefined;
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
      let confirmed: InvoiceEditorResponse;
      try {
        confirmed = await apiRequest<InvoiceEditorResponse>(
          `/api/v1/invoices/${saved.id}/confirm?tenant_id=${tenantId}`,
          {
            method: "POST",
            body: JSON.stringify({ expected_revision_id: saved.current_revision_id }),
          },
        );
      } catch (problem) {
        if (!(problem instanceof TypeError) || !browserOffline()) throw problem;
        try {
          await queueInvoiceConfirm(tenantId, membershipId, saved.id, saved.current_revision_id);
        } catch {
          throw problem;
        }
        setNotice(t("invoiceEditor.confirmQueuedOffline"));
        return;
      }
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
        `${tenantId}:${membershipId}:${customer.id}:${currency}:CUSTOMER_RECEIPT`,
        {
          customer_id: customer.id,
          amount: receiptAmount,
          currency,
          method: receiptMethod || null,
          reference: receiptReference || null,
          allocations: selectedAllocations,
        },
      );
      let payment: CustomerPaymentResponse;
      try {
          payment = await apiRequest<CustomerPaymentResponse>(
          `/api/v1/payments/customer-receipts?tenant_id=${tenantId}`,
          {
            method: "POST",
            body: JSON.stringify(command.payload),
          },
        );
      } catch (problem) {
        if (!(problem instanceof TypeError) || !browserOffline()) throw problem;
        const body = command.payload as { idempotency_key: string; customer_id: string; amount: string; currency: string; method?: string | null; reference?: string | null; paid_at: string; allocations?: Record<string, unknown>[] | null };
        try {
          await queueReceipt(tenantId, membershipId, body); // same idempotency key: the server replays, never double-charges
        } catch {
          throw problem; // no local queue (D-044): keep the intent for a manual retry
        }
        retireFinancialIntent(command);
        setNotice(t("invoiceEditor.receiptQueuedOffline"));
        return;
      }
      // A response arriving after navigation was not presented to the owner. Preserve it for replay.
      if (!mounted.current) return;
      retireFinancialIntent(command);
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
        `${tenantId}:${membershipId}:${customer.id}:${currency}:CUSTOMER_REFUND`,
        {
          customer_id: customer.id,
          amount: refundAmount,
          currency,
          method: refundMethod || null,
          reference: null,
        },
      );
      const refund = await apiRequest<CustomerPaymentResponse>(
        `/api/v1/payments/customer-refunds?tenant_id=${tenantId}`,
        {
          method: "POST",
          body: JSON.stringify(command.payload),
        },
      );
      if (!mounted.current) return;
      retireFinancialIntent(command);
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

  // ---------- presentation (slice 2): views over the same state and handlers ----------
  const goToCustomerStep = () => {
    setView("invoice");
    requestAnimationFrame(() => customerPhoneInput.current?.focus());
  };
  const openRevision = () => {
    setRevising(true);
    requestAnimationFrame(() => revisionTitle.current?.focus());
  };
  const closeRevision = () => {
    setRevising(false);
    requestAnimationFrame(() => documentTitle.current?.focus());
  };
  // A confirmed or cancelled invoice reads as a document; a confirmed one reopens in the existing
  // editor for a new revision. Drafts and new invoices stay in the editor.
  const showDocument = saved !== undefined && (saved.status === "CANCELLED" || (saved.status === "CONFIRMED" && !revising));
  const basisLabel = (basis: ProductPriceBasis) => t(basis === "BOX" ? "tenantWorkspace.box" : "tenantWorkspace.piece");
  const priceSourceLabel = (item: InvoiceEditorItem) => item.price_source === "EXPLICIT_GRADE_PRICE" ? t("invoiceEditor.explicitGradePrice") : item.price_source === "GRADE_DISCOUNT" ? t("invoiceEditor.gradeDiscount", { value: item.grade_discount_percent }) : t("invoiceEditor.normalPrice");
  const snapshotText = (key: string) => {
    const value = saved?.customer_snapshot[key];
    return typeof value === "string" ? value : undefined;
  };
  // Items and totals of one revision, exactly as the server returned them (never mixed with another revision).
  const itemsTable = (items: InvoiceEditorItem[], currencyCode: string, caption: string) => items.length ? (
    <table className="document-lines">
      <caption className="sr-only">{caption}</caption>
      <thead><tr><th scope="col">{t("orders.item")}</th><th scope="col">{t("orders.lineTotal")}</th></tr></thead>
      <tbody>
        {items.map((item) => (
          <tr key={item.id}>
            <td><strong>{item.product_name}</strong><small><bdi dir="ltr">{item.quantity}</bdi> {basisLabel(item.price_basis)} × <bdi dir="ltr">{money(item.effective_unit_price, currencyCode)}</bdi> · {priceSourceLabel(item)}</small></td>
            <td><bdi dir="ltr">{money(item.line_total, currencyCode)}</bdi></td>
          </tr>
        ))}
      </tbody>
    </table>
  ) : <p className="empty-copy">{t("invoiceEditor.emptyTitle")}</p>;
  const totalsList = (source: InvoiceEditorResponse) => (
    <dl className="document-totals">
      <div><dt>{t("invoiceEditor.previousBalance")}</dt><dd dir="ltr">{money(source.prior_balance, source.currency)}</dd></div>
      <div><dt>{t("invoiceEditor.subtotal")}</dt><dd dir="ltr">{money(source.subtotal, source.currency)}</dd></div>
      <div><dt>{t("invoiceEditor.discounts")}</dt><dd dir="ltr">{`− ${money(source.discount_total, source.currency)}`}</dd></div>
      <div><dt>{t("invoiceEditor.markups")}</dt><dd dir="ltr">{`+ ${money(source.markup_total, source.currency)}`}</dd></div>
      <div className="net-sales"><dt>{t("invoiceEditor.netSales")}</dt><dd dir="ltr">{money(source.net_sales, source.currency)}</dd></div>
      <div className="total-due"><dt>{t("invoiceEditor.totalDue")}</dt><dd dir="ltr">{money(source.total_due, source.currency)}</dd></div>
    </dl>
  );

  return (
    <div className="invoice-editor">
      <header className="invoice-editor-heading">
        <div>
          <p className="section-kicker">{t("invoiceEditor.kicker")}</p>
          <h3>{t("invoiceEditor.tab")}</h3>
        </div>
      </header>

      {/* One shared context for every view: the selected customer and the invoice currency. */}
      <section aria-label={t("invoiceEditor.context")} className="invoice-context">
        <div className="invoice-context-customer">
          {customer ? (
            <>
              <span className="grade-seal"><span className="sr-only">{t("tenantWorkspace.grade")} </span>{customer.grade ?? "—"}</span>
              <div><strong>{customer.name}</strong><small><bdi dir="ltr">{customer.phone}</bdi>{customer.address ? <> · {customer.address}</> : null}</small></div>
              {!saved || saved.status === "DRAFT" ? <button className="text-button" onClick={() => { setCustomer(undefined); goToCustomerStep(); }} type="button">{t("common.change")}</button> : null}
            </>
          ) : <span className="muted">{t("invoiceEditor.noCustomer")}</span>}
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
      </section>

      <div aria-label={t("invoiceEditor.views")} className="invoice-views" role="group">
        {INVOICE_VIEWS.map(([id, label]) => <button aria-controls={`invoice-view-${id}`} aria-pressed={view === id} key={id} onClick={() => setView(id)} type="button">{t(label)}</button>)}
      </div>

      {error ? <ErrorState error={error} /> : null}
      {notice ? <SuccessNotice>{notice}</SuccessNotice> : null}

      <section aria-label={t("invoiceEditor.viewInvoice")} className="invoice-view" hidden={view !== "invoice"} id="invoice-view-invoice">
      {showDocument && saved ? (
        <article aria-labelledby="invoice-document-title" className="invoice-document">
          <header className="document-head">
            <div>
              <p className="section-kicker">{t(saved.status === "CANCELLED" ? "invoiceEditor.cancelled" : "invoiceEditor.confirmed")}</p>
              <h4 id="invoice-document-title" ref={documentTitle} tabIndex={-1}><bdi dir="ltr">{saved.official_invoice_number ?? `R${saved.server_revision_number}`}</bdi></h4>
              <p className="document-tone">{t(saved.status === "CANCELLED" ? "invoiceEditor.cancelledTone" : "invoiceEditor.confirmedTone")}</p>
            </div>
          </header>
          <dl className="document-meta">
            <div><dt>{t("invoiceEditor.customerStep")}</dt><dd><strong>{snapshotText("name") ?? customer?.name ?? "—"}</strong>{snapshotText("phone") ?? customer?.phone ? <bdi dir="ltr">{snapshotText("phone") ?? customer?.phone}</bdi> : null}</dd></div>
            <div><dt>{t("tenantWorkspace.currency")}</dt><dd><bdi dir="ltr">{saved.currency}</bdi></dd></div>
            {saved.confirmed_at ? <div><dt>{t("invoiceEditor.confirmedAt")}</dt><dd><time dateTime={saved.confirmed_at}>{new Date(saved.confirmed_at).toLocaleString()}</time></dd></div> : null}
            <div><dt>{t("invoiceEditor.revision")}</dt><dd><bdi dir="ltr">R{saved.server_revision_number}</bdi></dd></div>
          </dl>
          <div className="document-body">
            {itemsTable(saved.items, saved.currency, t("invoiceEditor.invoiceLines"))}
            <div className="document-summary">
              {totalsList(saved)}
              <p className="backend-note snapshot-note">{t("invoiceEditor.totalDueNote")}</p>
            </div>
          </div>
          {openedByLink ? (
            <footer className="document-actions read-only">
              <p className="backend-note">{t("invoiceEditor.readOnlyFromLink")}</p>
              <Link className="text-button" to={sectionHref("invoices", tenantId)}>{t("invoiceEditor.newInvoice")}</Link>
            </footer>
          ) : saved.status === "CONFIRMED" ? (
            <footer className="document-actions">
              <button className="button" disabled={busy} onClick={openRevision} type="button">{t("invoiceEditor.createRevision")}</button>
              <div className="cancel-controls"><label className="field"><span>{t("invoiceEditor.cancellationReason")}</span><input value={cancelReason} onChange={(event) => setCancelReason(event.target.value)} /></label><button className="button button-danger" disabled={busy} onClick={cancelSaved} type="button">{t("invoiceEditor.cancelInvoice")}</button></div>
            </footer>
          ) : null}
        </article>
      ) : (
      <>
      {saved?.status === "CONFIRMED" ? (
        <div className="revision-bar">
          <p ref={revisionTitle} tabIndex={-1}>{t("invoiceEditor.revisingTitle")} <bdi dir="ltr">{saved.official_invoice_number}</bdi></p>
          <button className="text-button" onClick={closeRevision} type="button"><Arrow back small />{t("invoiceEditor.backToDocument")}</button>
        </div>
      ) : null}
      <div className="invoice-editor-grid">
        <div className="invoice-entry-desk">
          {customer ? null : (
          <article className="content-card invoice-customer-card">
            <p className="section-kicker">{t("invoiceEditor.customerStep")}</p>
            <h4>{t("invoiceEditor.findCustomer")}</h4>
                <form className="inline-form" onSubmit={searchCustomers}>
                  <label className="field">
                    <span>{t("fields.phone")}</span>
                    <input dir="ltr" ref={customerPhoneInput} required value={customerPhone} onChange={(event) => setCustomerPhone(event.target.value)} />
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
          </article>
          )}

          <article className="content-card item-entry-card">
            <p className="section-kicker">{t("invoiceEditor.itemStep")}</p>
            <h4>{t("invoiceEditor.addItems")}</h4>
            {/* One entry method at a time (barcode first); the others stay mounted, so typed values persist. */}
            <div aria-label={t("invoiceEditor.entryMethods")} className="entry-switch" role="group">
              {ENTRY_METHODS.map(([id, label]) => <button aria-controls={`entry-method-${id}`} aria-pressed={entryMethod === id} key={id} onClick={() => setEntryMethod(id)} type="button">{t(label)}</button>)}
            </div>
            <div className="entry-methods">
              <form className="entry-method" hidden={entryMethod !== "barcode"} id="entry-method-barcode" onSubmit={scanBarcode}>
                <div className="inline-form"><input aria-label={t("tenantWorkspace.barcode")} dir="ltr" required value={barcode} onChange={(event) => setBarcode(event.target.value)} /><button className="button" disabled={busy} type="submit">{t("tenantWorkspace.scan")}</button></div>
              </form>
              <form className="entry-method" hidden={entryMethod !== "catalog"} id="entry-method-catalog" onSubmit={searchCatalog}>
                <div className="inline-form"><input aria-label={t("invoiceEditor.catalogSearch")} required value={catalogQuery} onChange={(event) => setCatalogQuery(event.target.value)} /><button className="button button-secondary" disabled={busy} type="submit">{t("common.search")}</button></div>
                <div className="catalog-match-buttons">{catalogMatches.map((match) => <button key={match.product_id} onClick={() => addLine(productLine(match))} type="button"><strong>{match.name}</strong><span>{money(match.unit_price, match.currency)}</span></button>)}</div>
              </form>
              <form className="entry-method text-list-method" hidden={entryMethod !== "text"} id="entry-method-text" onSubmit={parseText}>
                <textarea aria-label={t("invoiceEditor.textEntry")} placeholder={t("invoiceEditor.textPlaceholder")} required rows={4} value={textList} onChange={(event) => setTextList(event.target.value)} />
                <button className="button button-secondary" disabled={busy} type="submit">{t("invoiceEditor.parseList")}</button>
              </form>
              <form className="entry-method manual-entry-method" hidden={entryMethod !== "manual"} id="entry-method-manual" onSubmit={addManual}>
                <input aria-label={t("invoiceEditor.itemName")} placeholder={t("invoiceEditor.itemName")} required value={manualName} onChange={(event) => setManualName(event.target.value)} />
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
                <div className="line-fields">
                <label className="field"><span>{t("invoiceEditor.quantityExpression")}</span><input dir="ltr" value={line.quantity} onChange={(event) => changeLine(line.key, { quantity: event.target.value })} /></label>
                <label className="field"><span>{t("tenantWorkspace.priceBasis")}</span><select value={line.basis} onChange={(event) => { const basis = event.target.value as ProductPriceBasis; changeLine(line.key, { basis, barcode: undefined }); void loadCostOptions({ ...line, basis, barcode: undefined }).catch(setError); }}><option value="PIECE">{t("tenantWorkspace.piece")}</option><option value="BOX">{t("tenantWorkspace.box")}</option></select></label>
                <label className="field"><span>{t("invoiceEditor.lineDiscount")}</span><input dir="ltr" value={line.lineDiscount} onChange={(event) => changeLine(line.key, { lineDiscount: event.target.value })} /></label>
                <label className="field"><span>{t("invoiceEditor.lineMarkup")}</span><input dir="ltr" value={line.lineMarkup} onChange={(event) => changeLine(line.key, { lineMarkup: event.target.value })} /></label>
                </div>
                {line.costOptions.length ? <div className="line-cost-controls"><label className="field"><span>{t("invoiceEditor.supplierCost")}</span><select value={line.supplierId ?? ""} onChange={(event) => changeLine(line.key, { supplierId: event.target.value })}><option value="">—</option>{line.costOptions.map((option) => <option key={option.supplier_id} value={option.supplier_id}>{option.supplier_name} · {option.unit_cost ?? "—"} {option.currency}{option.is_preferred ? ` · ${t("invoiceEditor.preferred")}` : ""}</option>)}</select></label><label className="field"><span>{t("invoiceEditor.costOverride")}</span><input dir="ltr" min="0" step="0.0001" type="number" value={line.costOverride} onChange={(event) => changeLine(line.key, { costOverride: event.target.value })} /></label>{line.costOverride ? <label className="field field-wide"><span>{t("invoiceEditor.overrideReason")}</span><input required value={line.costOverrideReason} onChange={(event) => changeLine(line.key, { costOverrideReason: event.target.value })} /></label> : null}</div> : null}
                {!line.productId && suppliers.length ? <div className="line-cost-controls"><label className="field"><span>{t("invoiceEditor.manualLineCost")}</span><select value={line.supplierId ?? ""} onChange={(event) => changeLine(line.key, { supplierId: event.target.value || undefined })}><option value="">—</option>{suppliers.map((supplier) => <option key={supplier.id} value={supplier.id}>{supplier.name}</option>)}</select></label><label className="field"><span>{t("invoiceEditor.costOverride")}</span><input dir="ltr" min="0" step="0.0001" type="number" value={line.costOverride} onChange={(event) => changeLine(line.key, { costOverride: event.target.value })} /></label>{line.costOverride ? <label className="field field-wide"><span>{t("invoiceEditor.overrideReason")}</span><input required value={line.costOverrideReason} onChange={(event) => changeLine(line.key, { costOverrideReason: event.target.value })} /></label> : null}</div> : null}
                {(line.productId ? !line.costOptions.some((option) => option.unit_cost !== null) : suppliers.length === 0) && !line.costOverride ? <p className="cost-missing" role="note">{t("invoiceEditor.costMissing")}{onOpenSupplierSetup ? <> <button className="text-button" onClick={onOpenSupplierSetup} type="button">{t("invoiceEditor.openSupplierSetup")}</button></> : null}</p> : null}
                <button className="text-button danger-link remove-line" onClick={() => setLines((current) => current.filter((item) => item.key !== line.key))} type="button">{t("common.remove")}</button>
              </article>
            ))}
            {!lines.length ? <div className="invoice-empty-lines"><strong>{t("invoiceEditor.emptyTitle")}</strong><span>{t("invoiceEditor.emptyBody")}</span></div> : null}
          </section>
        </div>

        <aside className="invoice-tally" aria-label={t("invoiceEditor.totals")}>
          <div className="tally-top"><span>{t(saved?.status === "CONFIRMED" ? "invoiceEditor.confirmed" : saved?.status === "CANCELLED" ? "invoiceEditor.cancelled" : "invoiceEditor.draft")}</span><strong><bdi dir="ltr">{saved?.official_invoice_number ?? (saved ? `R${saved.server_revision_number}` : "R—")}</bdi></strong></div>
          <dl>
            <div><dt>{t("invoiceEditor.previousBalance")}</dt><dd dir="ltr">{saved ? money(saved.prior_balance, saved.currency) : "—"}</dd></div>
            <div><dt>{t("invoiceEditor.subtotal")}</dt><dd dir="ltr">{saved ? money(saved.subtotal, saved.currency) : "—"}</dd></div>
            <div><dt>{t("invoiceEditor.discounts")}</dt><dd dir="ltr">{saved ? `− ${money(saved.discount_total, saved.currency)}` : "—"}</dd></div>
            <div><dt>{t("invoiceEditor.markups")}</dt><dd dir="ltr">{saved ? `+ ${money(saved.markup_total, saved.currency)}` : "—"}</dd></div>
            <div className="net-sales"><dt>{t("invoiceEditor.netSales")}</dt><dd dir="ltr">{saved ? money(saved.net_sales, saved.currency) : "—"}</dd></div>
            <div className="total-due"><dt>{t("invoiceEditor.totalDue")}</dt><dd dir="ltr">{saved ? money(saved.total_due, saved.currency) : "—"}</dd></div>
          </dl>
          {saved ? <p className="backend-note snapshot-note">{t("invoiceEditor.totalDueNote")}</p> : null}
          <div className="tally-adjustments"><label className="field"><span>{t("invoiceEditor.invoiceDiscount")}</span><input dir="ltr" value={invoiceDiscount} onChange={(event) => setInvoiceDiscount(event.target.value)} /></label><label className="field"><span>{t("invoiceEditor.invoiceMarkup")}</span><input dir="ltr" value={invoiceMarkup} onChange={(event) => setInvoiceMarkup(event.target.value)} /></label></div>
          {saved?.items.map((item) => <div className="saved-line-proof" key={item.id}>{item.media_snapshot.images?.[0]?.url ? <InvoiceLineImage name={item.product_name} url={item.media_snapshot.images[0].url} /> : null}<strong>{item.product_name}</strong><span>{item.price_source === "EXPLICIT_GRADE_PRICE" ? t("invoiceEditor.explicitGradePrice") : item.price_source === "GRADE_DISCOUNT" ? t("invoiceEditor.gradeDiscount", { value: item.grade_discount_percent }) : t("invoiceEditor.normalPrice")}</span><bdi dir="ltr">{money(item.line_total, saved.currency)}</bdi>{item.unit_cost ? <small>{t("invoiceEditor.costSnapshot", { value: item.unit_cost, currency: item.cost_currency })}</small> : null}</div>)}
          {saved?.status !== "CANCELLED" ? <button className="button tally-save" disabled={busy || !customer || !lines.length} onClick={saveDraft} type="button">{busy ? t("common.saving") : t(saved?.status === "CONFIRMED" ? "invoiceEditor.saveConfirmedRevision" : saved ? "invoiceEditor.recalculate" : "invoiceEditor.saveDraft")}</button> : null}
          {saved?.status === "DRAFT" ? <button className="button button-confirm" disabled={busy} onClick={confirmSaved} type="button">{t("invoiceEditor.confirmInvoice")}</button> : null}
          {saved && saved.status !== "CANCELLED" ? <div className="cancel-controls"><label className="field"><span>{t("invoiceEditor.cancellationReason")}</span><input value={cancelReason} onChange={(event) => setCancelReason(event.target.value)} /></label><button className="button button-danger" disabled={busy} onClick={cancelSaved} type="button">{t("invoiceEditor.cancelInvoice")}</button></div> : null}
          <p className="backend-note">{t("invoiceEditor.backendNote")}</p>
        </aside>
      </div>
      </>
      )}
      {showDocument && saved?.status === "CONFIRMED" ? (
        <NextSteps invoice={saved} onRecordPayment={() => { setPaymentFor({ id: saved.id, number: saved.official_invoice_number, applied: false }); setView("payments"); }} showInvoice={false} showSharing={false} tenantId={tenantId} />
      ) : null}
      {/* Mounted while the invoice is confirmed, whether the document or the revision editor shows, so a
          just-issued link stays visible until the owner leaves. */}
      {saved?.status === "CONFIRMED" ? <InvoiceSharing key={saved.id} tenantId={tenantId} invoiceId={saved.id} /> : saved ? <p className="backend-note">{t("invoiceEditor.sharingAfterConfirmation")}</p> : null}
      {history?.revisions.length ? (
        <section aria-labelledby="invoice-history-title" className="invoice-history">
          <h4 id="invoice-history-title">{t("invoiceEditor.revisionHistory")}</h4>
          {/* Each entry opens to that revision's own items and totals, read-only, as the server kept them. */}
          {history.revisions.map((revision) => (
            <details className={revision.is_current ? "is-current" : undefined} key={revision.current_revision_id}>
              <summary>
                <span className="revision-name"><strong>R{revision.server_revision_number}</strong>{revision.is_current ? <span className="current-mark">{t("invoiceEditor.currentRevision")}</span> : null}</span>
                <time dateTime={revision.revision_created_at}>{new Date(revision.revision_created_at).toLocaleString()}</time>
                <bdi className="revision-amount" dir="ltr">{money(revision.net_sales, revision.currency)}</bdi>
                {revision.ledger_delta !== null ? <small className="revision-delta" dir="ltr">Δ {money(revision.ledger_delta, revision.currency)}</small> : null}
              </summary>
              <div className="revision-detail">
                {revision.reason ? <p className="revision-reason"><span>{t("invoiceEditor.revisionReason")}</span> {revision.reason}</p> : null}
                {itemsTable(revision.items, revision.currency, `R${revision.server_revision_number} · ${t("invoiceEditor.invoiceLines")}`)}
                {totalsList(revision)}
              </div>
            </details>
          ))}
        </section>
      ) : null}
      </section>

      <section aria-label={t("invoiceEditor.viewPayments")} className="invoice-view" hidden={view !== "payments"} id="invoice-view-payments">
      <section className="settlement-desk" aria-labelledby="settlement-desk-title">
        <header>
          <div><p className="section-kicker">{t("invoiceEditor.settlementKicker")}</p><h3 id="settlement-desk-title">{t("invoiceEditor.settlementTitle")}</h3><p>{t("invoiceEditor.settlementBody")}</p></div>
        </header>
        {paymentFor && customer ? <p className="notice view-guide" role="note">{t("invoiceEditor.fromInvoice", { number: paymentFor.number ?? "…" })}</p> : null}
        {customer ? null : <div className="notice view-guide" role="note"><span>{t("invoiceEditor.chooseCustomerFirst")}</span><button className="text-button" onClick={goToCustomerStep} type="button">{t("invoiceEditor.goToCustomer")}</button></div>}
        <div className="settlement-grid">
          <article className="content-card obligation-card">
            <div className="settlement-card-heading"><div><span>01</span><h4>{t("invoiceEditor.openObligations")}</h4></div><div className="allocation-mode" role="group" aria-label={t("invoiceEditor.allocationMode")}><button aria-pressed={allocationMode === "FIFO"} onClick={() => setAllocationMode("FIFO")} type="button">{t("invoiceEditor.fifoAllocation")}</button><button aria-pressed={allocationMode === "OWNER"} onClick={() => setAllocationMode("OWNER")} type="button">{t("invoiceEditor.ownerAllocation")}</button></div></div>
            {obligations?.obligations.length ? <div className="obligation-list">{obligations.obligations.map((obligation) => <label className={`obligation-row${paymentFor && obligation.source_id === paymentFor.id ? " is-context" : ""}`} key={obligation.target_ledger_entry_id}><span>{obligation.source_type === "INVOICE" && obligation.source_id ? <Link to={sectionHref("invoices", tenantId, { invoice: obligation.source_id })}><strong>{obligation.label}</strong></Link> : <strong>{obligation.label}</strong>}<time dateTime={obligation.effective_at}>{new Date(obligation.effective_at).toLocaleDateString()}</time></span><bdi dir="ltr">{money(obligation.outstanding_amount, currency)}</bdi>{allocationMode === "OWNER" ? <input aria-label={t("invoiceEditor.allocateTo", { label: obligation.label })} dir="ltr" max={obligation.outstanding_amount} min="0" placeholder="0.0000" step="0.0001" type="number" value={allocationAmounts[obligation.target_ledger_entry_id] ?? ""} onChange={(event) => setAllocationAmounts((current) => ({ ...current, [obligation.target_ledger_entry_id]: event.target.value }))} /> : <span className="fifo-mark">{t("invoiceEditor.fifoQueued")}</span>}</label>)}</div> : <p className="empty-copy">{t("invoiceEditor.noOpenObligations")}</p>}
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
      </section>

      <section aria-label={t("invoiceEditor.viewBalances")} className="invoice-view" hidden={view !== "balances"} id="invoice-view-balances">
      <section className="debt-desk" aria-labelledby="debt-desk-title">
        <header><div><p className="section-kicker">{t("invoiceEditor.debtKicker")}</p><h3 id="debt-desk-title">{t("invoiceEditor.debtTitle")}</h3></div><form className="threshold-form" onSubmit={saveOverdueThreshold}><label className="field"><span>{t("invoiceEditor.overdueThreshold")}</span><input dir="ltr" min="0" type="number" value={overdueThreshold} onChange={(event) => setOverdueThreshold(event.target.value)} /></label><button className="button button-secondary" disabled={busy} type="submit">{t("common.saveChanges")}</button></form></header>
        <div className="debt-desk-grid">
          <article className="content-card opening-balance-card"><h4>{t("invoiceEditor.openingBalance")}</h4><p>{t("invoiceEditor.openingBalanceBody")}</p>{customer ? <><strong>{customer.name}</strong><div className="balance-chips">{balances?.balances.length ? balances.balances.map((balance) => <span dir="ltr" key={balance.currency}>{money(balance.balance, balance.currency)}</span>) : <span>{t("invoiceEditor.noLedgerBalance")}</span>}</div></> : null}<form className="form-grid" onSubmit={recordOpeningBalance}><label className="field"><span>{t("invoiceEditor.signedOpeningAmount")}</span><input dir="ltr" required step="0.0001" type="number" value={openingAmount} onChange={(event) => setOpeningAmount(event.target.value)} /></label><label className="field"><span>{t("tenantWorkspace.currency")}</span><input dir="ltr" maxLength={3} minLength={3} required value={openingCurrency} onChange={(event) => setOpeningCurrency(event.target.value.toUpperCase())} /></label><label className="field field-wide"><span>{t("invoiceEditor.effectiveAt")}</span><input required type="datetime-local" value={openingEffectiveAt} onChange={(event) => setOpeningEffectiveAt(event.target.value)} /></label><button className="button field-wide" disabled={busy || !customer} type="submit">{t("invoiceEditor.recordOpeningBalance")}</button></form></article>
          <article className="content-card debt-register"><h4>{t("invoiceEditor.customerDebt")}</h4>{debts.debts.length ? debts.debts.map((debt) => <div className={debt.is_overdue ? "debt-row is-overdue" : "debt-row"} key={`${debt.customer_id}-${debt.currency}`}><span className="debt-alert-mark" aria-hidden="true">{debt.is_overdue ? "!" : "·"}</span><div><strong>{debt.customer_name}</strong><bdi dir="ltr">{debt.customer_phone}</bdi></div><bdi className="debt-amount" dir="ltr">{money(debt.balance, debt.currency)}</bdi><span>{debt.is_overdue ? t("invoiceEditor.overdueBy", { days: debt.overdue_age_days }) : t("invoiceEditor.currentDebt")}</span></div>) : <p className="empty-copy">{t("invoiceEditor.noCustomerDebt")}</p>}</article>
        </div>
      </section>
      </section>
    </div>
  );
}
