# Pricing contract

Price precedence is explicit product-grade price, then grade percentage discount, then normal product price. Initial grades are A+, A, B+, and B. Piece/box counterpart pricing must be derived consistently. The backend uses decimal arithmetic with `ROUND_HALF_UP`; PostgreSQL stores money as `NUMERIC(20,4)`. Currencies are never silently mixed.
