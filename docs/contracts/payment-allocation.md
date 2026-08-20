# Payment allocation contract

Customer payments and allocations are immutable. Allocation and reversal semantics preserve the append-only ledger, transactionally enforce balance/refund invariants, and never silently mix currencies. Supplier payments reduce aggregate supplier payable; per-purchase allocation is not approved.
