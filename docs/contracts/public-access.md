# Public access contract

Storefront customers are not application users and need no login, verified account, email, password, or age (accounts are never globally mandatory; an owner-issued personalized link — D-071 — or, later, optional verification/accounts — D-073/D-074 — may add assurance). Phone is required for checkout/search but never authorizes prior customer data. Public invoices use random capability tokens; internal IDs do not authorize access. Token responses are `no-store`, `noindex`, and `no-referrer`, and tokens are not logged.

Rate limits are operational policy (D-076): defaults 60 requests/minute/IP for private invoice links and the customer-context endpoint, 600/minute/IP for the anonymous catalog, adjustable through configuration; they are never the only control.
