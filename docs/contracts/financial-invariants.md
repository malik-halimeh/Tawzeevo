# Financial invariants

Financial history is append-only. Confirmed invoice edits produce immutable revisions and ledger deltas. Customer balance is the currency-specific sum of signed ledger entries. Refunds cannot exceed available credit and must be serialized transactionally. Supplier payments reduce aggregate supplier payable; no per-purchase allocation is assumed.
