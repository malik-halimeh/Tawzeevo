# Owner intelligence — setup that only the owner can do

This file lists every step that needs the owner's own accounts, keys or approvals. Everything
else is already built and tested (see [README.md](README.md)).

**What works with no setup at all:** today's priorities (Work), the attention list and buying
rhythm (Customers), each customer's signals, the cash position and ageing, and unusual changes
(Analytics). These are calculated inside Tawzeevo from its own records and use no outside service.

**What needs setup:** only the **business assistant** (Workspace › More › Assistant). It sends a
question and a small set of figures to an outside language model to write the answer. Until a key
is set it shows **"The assistant is not switched on"**, and nothing else changes.

The provider is **Groq** (decision D-089 in `04_DECISIONS.md`). Changing provider is a new
decision, not a setting.

## Checklist

- [ ] 1. Groq account and organization ready
- [ ] 2. Model access and billing/limits checked
- [ ] 3. API key created for the live service
- [ ] 4. Key added to the live API service on Render (`GROQ_API_KEY`)
- [ ] 5. (Recommended) a separate key added to the staging API service
- [ ] 6. Status check says the assistant is configured
- [ ] 7. One real question answered in the workspace
- [ ] 8. (Optional) local development key for trying it on your own computer

Nothing is needed in GitHub Actions: CI never calls the provider (see step 4, "CI").

---

## 1. Groq account and organization

| | |
|---|---|
| What | A Groq Cloud account with an organization that will own the key |
| Why | The assistant sends requests to Groq's chat-completions API |
| Mandatory? | Only for the assistant. Optional for the rest of Tawzeevo |
| Service | Groq Cloud — <https://console.groq.com> |

Steps:

1. Open <https://console.groq.com> and sign in (or sign up) with the business e-mail you want
   to own the provider account.
2. If Groq asks you to create or pick an **organization**, create one named after the business
   (for example "Tawzeevo"). Keys belong to the organization, so a teammate you invite later can
   manage them without using your personal login.
3. In the organization's settings, review the data-usage / data-retention options Groq offers
   and choose the most private one available. Tawzeevo already limits what it sends (see
   "Security notes"), but the provider-side setting is yours to choose.

## 2. Model access, billing and limits

| | |
|---|---|
| What | Permission to call the model Tawzeevo uses, with enough request quota |
| Tawzeevo setting | `COPILOT_MODEL` (default `llama-3.3-70b-versatile`) |
| Mandatory? | Yes for the assistant |

Steps:

1. In the console, open **Docs › Models** (<https://console.groq.com/docs/models>) and confirm
   `llama-3.3-70b-versatile` is listed as a production model. It was listed on 2026-09-25.
   It must support **tool use** (function calling); Tawzeevo depends on it.
2. Open **Settings › Limits** (or **Billing**) for the organization:
   - On the free tier, check the per-minute and per-day request/token limits. One owner question
     is usually 2–5 provider calls (the model asks for one or more figures, then writes the
     answer). Tawzeevo itself also caps each owner at **30 questions per hour**
     (`COPILOT_REQUESTS_PER_HOUR`).
   - For regular use by several businesses, add a payment method and choose a paid plan, and set a
     monthly **spend limit** if the console offers one.
3. If Groq ever retires this model, choose another production model that supports tool use and
   set `COPILOT_MODEL` to its exact id (same place as the key, step 4). No code change is needed.

## 3. Create the API key

| | |
|---|---|
| Where | Groq console › **API Keys** (<https://console.groq.com/keys>) › **Create API Key** |
| Name it | `tawzeevo-live` (and later `tawzeevo-staging`, `tawzeevo-local`) |
| Format | A long secret string that starts with `gsk_` (never share or paste it anywhere but Render) |

Steps:

1. Click **Create API Key**, name it `tawzeevo-live`, and create it.
2. Copy the key immediately — Groq shows it only once.
3. Paste it straight into Render (step 4). Do not save it in a file, chat, ticket, e-mail or
   the repository.

Use one key per environment (live, staging, local) so each can be revoked alone.

## 4. Put the key on the live API service (Render)

| | |
|---|---|
| Tawzeevo variable | **`GROQ_API_KEY`** |
| Service | Render web service **`tawzeevo-api-malik-halimeh`** (the API, not the web client) |
| Already declared? | Yes — `render.yaml` lists `GROQ_API_KEY` with `sync: false`, so Render expects you to type the value in the dashboard; it is never stored in Git |

Steps:

1. Open <https://dashboard.render.com> › **tawzeevo-api-malik-halimeh** › **Environment**.
2. Find `GROQ_API_KEY` (or click **Add Environment Variable**), paste the `tawzeevo-live` key as
   the value, and save.
3. Deploy the change: Render offers **Save and deploy** (or **Save, rebuild and deploy**). The
   live services have automatic deploys off (`autoDeployTrigger: off`), so if you choose
   **Save only**, the key takes effect on the next deploy.
4. Optional settings on the same screen (leave them unset to keep the defaults):

| Variable | Default | What it does |
|---|---|---|
| `COPILOT_MODEL` | `llama-3.3-70b-versatile` | Groq model id |
| `COPILOT_TIMEOUT_SECONDS` | `20` | How long one provider call may take (1–60) |
| `COPILOT_REQUESTS_PER_HOUR` | `30` | Questions per owner per hour (1–500) |
| `COPILOT_MAX_TOOL_ROUNDS` | `4` | How many figure look-ups one answer may make (1–8) |

**Not needed:** no callback URL, redirect URI, allowed origin or domain allow-list — Groq is
called from the API server only, never from the browser. The web client (`tawzeevo-malik-halimeh`)
and the storefront need nothing; the key must **never** be added to them (browser bundles are
public).

**CI (GitHub Actions):** do **not** add the key as a GitHub secret. Every test replaces the
provider with a scripted stand-in and blanks `GROQ_API_KEY`, so CI never makes a paid call.

## 5. Staging (recommended)

The staging API (`tawzeevo-staging-api`, configured in the Render dashboard, not in
`render.yaml`) has its own database. Give it its **own** key (`tawzeevo-staging`), set as
`GROQ_API_KEY` on that service the same way. Or leave it unset: staging then shows the
not-switched-on state, which is also a valid thing to demonstrate.

## 6. Check that the server sees the key

Any of these, after the deploy finishes:

- **Render logs** of the API service at start-up show one line, and never the key:
  `business assistant configured` (or `business assistant not configured (GROQ_API_KEY unset)`).
- **In the workspace:** sign in as an owner › More › **Assistant**. The "not switched on" panel is
  replaced by suggested questions and a question box.
- **API:** `GET /api/v1/intelligence/copilot/status?tenant_id=<your business id>` as the owner
  returns `{"configured": true, "provider": "groq", "model": "llama-3.3-70b-versatile"}`. It never
  returns the key.

## 7. One real question

1. Open Assistant and click **"Who should I call today?"**.
2. Expected: an answer naming customers that also appear in **Customers › Needs attention**, a
   **"Based on:"** line (for example "Today's priorities · USD") and clickable customer names.
3. Compare one amount in the answer with Customers or Analytics. They must match; if the answer
   contains a figure Tawzeevo did not supply, a yellow **"Check these figures…"** note appears.

What you may see instead:

| Screen says | Meaning | What to do |
|---|---|---|
| The assistant is not switched on | `GROQ_API_KEY` is empty on the API service | Step 4, then deploy |
| The assistant's language service did not answer in time | Groq timed out, refused the key, or is rate-limited (HTTP 502 `COPILOT_PROVIDER_UNAVAILABLE`) | Check the key is correct and active, check Groq limits/billing, look at `copilot_provider_failures` in `GET /health/metrics` |
| You have asked many questions in the last hour | Tawzeevo's own 30/hour cap per owner (HTTP 429) | Wait, or raise `COPILOT_REQUESTS_PER_HOUR` |
| The assistant could not finish this answer | The model needed more than `COPILOT_MAX_TOOL_ROUNDS` look-ups | Ask a narrower question |

Nothing in any of these cases changes business data; the assistant has no write access.

## 8. Local development (optional)

To try the real assistant on your own computer: create a `tawzeevo-local` key and set it only in
the shell that starts the API, for example `GROQ_API_KEY=gsk_… uvicorn tawzeevo_api.main:app`,
or in your untracked local `.env` (already ignored by Git). Never put it in `apps/operations-web`
(`VITE_*` variables end up in the browser). Remove it from the shell before running tests; the
tests blank it anyway.

## Rotating or revoking the key

1. Groq console › API Keys › create a new key (e.g. `tawzeevo-live-2026-10`).
2. Render › API service › Environment › replace `GROQ_API_KEY` › save and deploy.
3. Ask one question to confirm (step 7).
4. Back in the Groq console, **delete** the old key.

If a key may have leaked: delete it in the Groq console first (the assistant then shows the
"did not answer" error until the new key is set), then create and set a new one.

## Security notes

- The key lives only in Render's environment settings (and, if you choose, your own shell). It
  is never committed, never sent to the browser, never logged, and `/copilot/status` never
  returns it.
- What leaves Tawzeevo for each question: the question, the earlier turns of that conversation,
  and the compact figures the model asked for (per currency). Customer names are replaced by
  references like `C-ABC234` before anything is sent and put back only inside Tawzeevo. Phones,
  addresses, locations, sign-in data, share links and other businesses' data are never sent.
  Nothing is stored — neither questions nor answers.
- Do not paste the key into support tickets, screenshots, chat, the repository or issue trackers.
  If it appears in any of these, revoke it.
