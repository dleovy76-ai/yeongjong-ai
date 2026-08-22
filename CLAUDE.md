# YEONGJONG AI — Project Rules

Full source-of-truth spec: [docs/MASTER_PLAN.md](docs/MASTER_PLAN.md) (61 sections, owner-authored). This file is the condensed, enforceable summary — when in doubt, the master plan wins.

## What this is

지역 AI 경제 플랫폼 for Yeongjong Island (영종도). Business owners get an "AI employee," visitors get an "AI travel guide." Growth loop: business signs up → AI assists customers → coupon/reservation → verified visit/transaction → performance shown to owner → **Expansion AI** finds and invites related businesses → network grows. The Expansion AI referral loop is the single most important mechanism in this product (see master plan §20-25, addendum) — prioritize proving it over adding agent count.

The one thing the MVP must prove: visitor asks → AI recommends a real business → coupon/reservation used → real visit → real transaction → owner says "I need to keep using this" → owner brings in another owner. If this loop doesn't close, nothing else matters yet.

## Non-negotiable product rules (master plan §1, §29, §55)

- Never sell "AI" itself — the product is owner time saved + real customers delivered.
- Never fabricate prices, hours, discounts, availability, or tourist info the AI doesn't actually have. If unconfirmed: respond "현재 확인되지 않은 정보입니다." — never guess.
- Never count a conversation or exposure as revenue. Use attribution tiers (§18): DIRECT / ASSISTED / INFLUENCED / UNKNOWN. Always show the attribution basis next to any revenue number in a dashboard.
- Recommendations rank on quality/relevance, not on who pays more. Paid promotion must be visibly labeled ("프로모션"/"제휴 혜택"), never disguised as an organic recommendation.
- All information the AI cites must be source-aware: `source`, `verified_at`, `expires_at`, `status` (VERIFIED/UNVERIFIED/EXPIRED/DISABLED). Expired info is never recommended.
- Business-specific facts live in that business's `BusinessContext` (§8) and are approved by the owner — agents answer from it, they don't invent around gaps.

## Engineering rules

- **Modular monolith only** at this stage — no microservices, no Kubernetes, no separate event bus, no separate graph DB, no custom LLM training (§59). Revisit only when real traffic forces it.
- **LLM provider abstraction from day one**: agents call an `LLMProvider` interface, never a specific vendor SDK directly, so no agent code is locked to one model (§4, §52).
- Agents never query the DB directly — they go through a `Tool` layer (`BusinessSearchTool`, `MenuSearchTool`, etc., §53) that mediates access.
- Every AI request gets observability fields logged: `request_id, user_id, business_id, agent, model, prompt_version, latency, token_usage, cost, success, error` (§42). Cost-route by question difficulty — don't send everything to the most expensive model (§43).
- Agent prompts are versioned data (`prompt_id, agent_type, version, content, status`), not hardcoded strings (§44) — conversation logs link back to the `prompt_version` that produced them.
- Route cheap/simple questions through rules/DB lookup and retrieval before ever calling an LLM (§43).

## Working method (master plan §50, §58)

Before implementing any feature: check current repo structure, existing models/APIs/tests, and reuse what's there — don't recreate or delete working code casually.

Every unit of work follows: **PLAN → FILES TO CHANGE → IMPLEMENT → TEST → VERIFY → REPORT**. Do not implement the whole project at once — go step by step per the dev order in master plan §51, and report what changed (features, files, DB, API, tests, open issues, next step) at the end of each unit.

## Dev order (master plan §51)

STEP1 repo structure → STEP2 DB → STEP3 auth → STEP4 business onboarding → STEP5 business context → STEP6 agent framework → STEP7-10 Manager/Customer/Chef/Info agents → STEP11 recommendation engine → STEP12 coupon → STEP13 reservation → STEP14 event tracking → STEP15 performance dashboard → STEP16 partner graph → STEP17 expansion AI → STEP18 referral → STEP19 admin → STEP20 pilot deploy.

## Stack

Backend: Python 3.11+, FastAPI, SQLAlchemy, Alembic, PostgreSQL, Redis, pgvector (for embeddings). Frontend: Next.js + TypeScript + Tailwind. Auth: JWT initially, social login (Google/Apple/Kakao) added incrementally. Multilingual from the start: ko/en/zh (ja later) — `BusinessContext` fields carry locale suffixes (`name_ko`, `name_en`, `name_zh`).

## Privacy

PII and location data are minimum-collection by default (§9, §49). Location is only used with explicit user opt-in, never forced. Keep marketing consent, cookies, behavioral logs, and reservation data in clearly separated storage/handling paths per Korean 개인정보보호법 considerations.
