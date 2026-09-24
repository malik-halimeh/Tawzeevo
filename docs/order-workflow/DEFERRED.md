# Order workflow fix — deferred items

Found during the work. None of these blocks M1–M4, so none was fixed here.

| # | Item | Evidence | Why deferred |
|---|---|---|---|
| F-01 | Storefront `error.tsx` and `not-found` pages link back to the shop without the tab's `?c=` context. | `app/[slug]/error.tsx`, `app/not-found.tsx` | Rare pages. Following the link lands on the bare shop address, which is the most recently opened link as before, so no identity is merged into an order without the server resolving it. |
| F-02 | The owner's in-panel notification counter is never marked read (`POST /notifications/{id}/read` has no caller). | `components/OrdersPanel.tsx`, `routes/storefront.py` | Existing behaviour. Read/unread state is out of scope (no new notification state). |
