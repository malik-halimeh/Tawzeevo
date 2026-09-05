# Financial invariants

Financial history is append-only. Confirmed invoice edits produce immutable revisions and ledger deltas. Customer balance is the currency-specific sum of signed ledger entries. Refunds cannot exceed available credit and must be serialized transactionally. Supplier payments reduce aggregate supplier payable; no per-purchase allocation is assumed.

Historical profit is revision-specific and must never be recomputed from the latest supplier price.
Every confirmed invoice revision line preserves an immutable unit-cost snapshot with its currency,
piece/box basis context, and source provenance. A later supplier price affects only later eligible sales;
it cannot alter prior invoice profit. Supplier costs and profit remain owner-only. Automatic cost-source
selection and any owner override workflow must be explicitly locked before the supplier/confirmed-
invoice integration is implemented.

D-034 locks that workflow. Supplier identities, preferred supplier selection, and append-only
product-cost entries are tenant-private; no tenant can inherit another tenant's negotiated cost.
Invoice entry uses the latest eligible matching cost for the selected or preferred supplier and
permits an owner-only, reasoned revision override. Confirmation requires matching currency and
snapshots the cost, basis/package context, supplier/source provenance, and override reason. An
override becomes a future default only through an explicit new cost entry. No stock, FIFO,
weighted-average costing, global supplier price, or silent currency conversion is implied.
