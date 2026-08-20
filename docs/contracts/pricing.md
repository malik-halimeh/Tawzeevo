# Pricing contract

Price precedence is explicit product-grade price, then grade percentage discount, then normal product price. Initial grades are A+, A, B+, and B. Piece/box counterpart pricing must be derived consistently. The backend uses decimal arithmetic with `ROUND_HALF_UP`; PostgreSQL stores money as `NUMERIC(20,4)`. Currencies are never silently mixed.

The Phase 1 product foundation stores one four-decimal `unit_price`, its `PIECE` or `BOX` basis, an explicit three-letter currency code, and optional `pieces_per_box`. A box-basis product requires `pieces_per_box`; counterpart prices are returned as four-decimal derived values. The basic draft invoice snapshots product name, barcode, price basis, and unit price, calculates line totals and subtotal on the backend, and rejects mixed currencies. It does not yet implement the later grade-pricing or immutable confirmed-invoice engine.
