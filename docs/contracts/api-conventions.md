# API conventions

Production APIs use `/api/v1`. Mandatory evaluator routes remain at their exact root paths. Timestamps use RFC3339 and currencies use ISO codes. Authentication failures are `401`, authorization failures `403`, missing resources `404`, and state/uniqueness conflicts `409`; Pydantic validation retains `422` semantics. OpenAPI remains usable and password/hash values are never returned.

Tenant business resources are nested below `/api/v1/tenants/{tenant_id}`. The tenant identifier is a requested scope, not authorization; active membership and lifecycle checks precede each operation. Tenant-owned identifiers queried under the caller's valid tenant return `404` when the record belongs elsewhere, while attempting to enter a tenant without membership returns `403`.
