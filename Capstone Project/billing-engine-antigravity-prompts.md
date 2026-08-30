# Usage Metering & Billing Engine — Antigravity Build Guide

How to use this: work through the phases in order. Paste each prompt into a **new Antigravity conversation** (or continue in the same one if the context is still relevant), let the agent plan and execute, then **review the plan before it runs** and test the result before moving to the next phase. Don't paste all prompts at once — Antigravity works best when it can finish and verify one chunk before taking on the next.

---

## Phase 1 — Project scaffold

```
Set up a new backend project for a usage metering and billing engine.

Stack: FastAPI, PostgreSQL, SQLAlchemy (or your preferred ORM), Redis for caching, Alembic for migrations. Python 3.11+.

Requirements:
- Project structure with clear separation: api/routes, models, services, db, core/config
- Environment-based config (.env) for DB URL, Redis URL, Stripe keys (use placeholders for now)
- A health-check endpoint at /health
- Docker Compose file to run the API, Postgres, and Redis locally
- README with setup instructions

Do not add business logic yet — just get a clean, runnable skeleton with the health-check working end to end.
```

---

## Phase 2 — Database schema

```
Design and implement the database schema for the billing engine using SQLAlchemy models and Alembic migrations.

Tables needed:
- customers: id, email, name, created_at
- plans: id, name (Free/Pro), monthly_quota, price_cents
- subscriptions: id, customer_id, plan_id, status (active/canceled/past_due), stripe_subscription_id, current_period_start, current_period_end
- usage_events: id, customer_id, endpoint, units, idempotency_key (unique), created_at
- invoices: id, customer_id, period_start, period_end, total_cost_cents, status

Add appropriate foreign keys, indexes (especially on idempotency_key and customer_id), and a seed script that creates a Free and Pro plan.

Explain the schema decisions briefly when done, and run the migration to confirm it applies cleanly.
```

---

## Phase 3 — Auth and customer/plan endpoints

```
Add authentication and core CRUD endpoints to the billing engine.

Requirements:
- API-key based authentication: each customer gets a unique API key, sent via an "Authorization: Bearer <key>" header
- Endpoint to create a customer (assigns them to the Free plan by default and generates their API key)
- Endpoint to fetch the current authenticated customer's profile, plan, and quota
- Endpoint to list available plans
- Proper error handling for missing/invalid API keys (401)

Write tests for: valid auth succeeds, missing key fails, invalid key fails, new customer defaults to Free plan.
```

---

## Phase 4 — Metered endpoint with idempotency

```
Build the core metered API endpoint and idempotent usage logging.

Requirements:
- A sample "billable" endpoint (e.g. POST /v1/usage) that authenticated customers call to simulate using the product
- Accepts an idempotency key from the client (header: Idempotency-Key), or generate one server-side if absent
- Before logging usage, check if that idempotency_key already exists for this customer — if so, return the previous result without logging again
- If new, insert a usage_event row and return success
- Write tests that specifically prove duplicate requests with the same idempotency key are only counted once, including a test that fires the same request twice in quick succession
```

---

## Phase 5 — Quota enforcement with caching

```
Add quota enforcement to the metered endpoint using Redis for fast lookups.

Requirements:
- Maintain a Redis counter per customer per billing period (e.g. key: usage:{customer_id}:{year}-{month}) that increments on each successfully logged usage_event
- Before processing a request, check this counter against the customer's plan monthly_quota
- If quota exceeded, return 429 Too Many Requests with a clear error message
- If the Redis counter is missing (cache miss, e.g. after Redis restart), rebuild it from usage_events for the current period, then proceed
- Write tests for: under quota succeeds, at quota limit fails, cache rebuild works correctly after a simulated Redis miss
```

---

## Phase 6 — Cost calculation and reporting

```
Add cost calculation and a usage reporting endpoint.

Requirements:
- A function that, given a customer and billing period, calculates total cost based on their plan (flat monthly fee for Pro, and a simple per-unit overage charge for usage beyond the Free quota)
- Endpoint GET /v1/usage/summary that returns the authenticated customer's usage this period, quota, percentage used, and current estimated cost
- Endpoint GET /v1/usage/history for a simple time-series of daily/weekly usage, suitable for charting
- Write tests confirming cost calculation is correct for a few example scenarios (under quota, over quota, Pro plan)
```

---

## Phase 7 — Stripe integration and webhooks

```
Integrate Stripe test mode for plan upgrades.

Requirements:
- Endpoint POST /v1/billing/checkout that creates a Stripe Checkout Session (test mode) for upgrading the authenticated customer from Free to Pro, and returns the checkout URL
- Webhook endpoint POST /v1/webhooks/stripe that:
  - Verifies the Stripe signature using the webhook secret
  - Handles checkout.session.completed: create/update the subscription record, move the customer to the Pro plan
  - Handles customer.subscription.updated and customer.subscription.deleted: keep local subscription status in sync
- Store the Stripe customer ID and subscription ID on our records so future webhook events can be matched back to the right customer
- Document how to test this locally using the Stripe CLI (stripe listen --forward-to localhost:8000/v1/webhooks/stripe)
- Write tests using Stripe's test event payloads to confirm webhook handling updates the DB correctly, including a test for an invalid/unverifiable signature being rejected
```

---

## Phase 8 — Background jobs

```
Add background job handling for periodic tasks.

Requirements:
- Use a lightweight scheduler suitable for this project (APScheduler is fine for a capstone; Celery + Redis if you want the extra complexity)
- Job 1: at the start of each billing period, reset/rebuild the Redis usage counters
- Job 2: generate an invoice record (from Phase 6's cost calculation) for each customer at the end of their billing period
- Make sure jobs are idempotent themselves — running the same job twice for the same period shouldn't create duplicate invoices
- Add logging so job runs are visible/debuggable
```

---

## Phase 9 — Frontend dashboard

```
Build a simple frontend dashboard for customers to view their usage and manage billing.

Stack: React (Vite), plain CSS or Tailwind — keep it clean and minimal, not over-designed.

Pages:
- Login/API key entry (store the key in memory for the session, send as Bearer token to the API)
- Dashboard: current plan, quota used vs. limit (progress bar), estimated cost this period
- Usage history: simple line/bar chart of usage over time (use the /v1/usage/history endpoint)
- Upgrade button: calls /v1/billing/checkout and redirects the browser to the returned Stripe Checkout URL
- A "billing updated" success/cancel page for after Stripe checkout redirects back

Keep API calls in a small dedicated service file, not scattered inline. Handle loading and error states for each page.
```

---

## Phase 10 — Testing, docs, and deployment

```
Finish the project for portfolio/submission readiness.

Requirements:
- Run through and confirm all test suites pass (auth, idempotency, quota, cost calculation, webhooks)
- Add a top-level README covering: what the project does, architecture overview, how to run it locally (backend + frontend + Docker Compose), how to test the Stripe webhook flow with the Stripe CLI, and a list of the backend concepts demonstrated (API design, database, auth, background jobs, caching, reporting)
- Add basic API documentation (FastAPI gives you /docs for free — just make sure endpoint descriptions and request/response models are clear)
- Suggest a simple deployment path (e.g. Railway/Render for the API + Postgres + Redis, Vercel/Netlify for the frontend) and scaffold whatever config files are needed
```

---

## Notes on working with Antigravity

- After each phase's prompt, Antigravity will produce a plan before executing — **read it**. If it's about to do something you didn't ask for (e.g. adding auth providers you don't need), correct it before it runs.
- Point it at specific files with `@filename` when you want it to build on existing code rather than starting fresh.
- If a phase fails partway (e.g. Stripe webhook tests), it's fine to re-run just that phase's prompt with an added note like "the previous attempt failed on signature verification — check the webhook secret is loaded from env correctly."
