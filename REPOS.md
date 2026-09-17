# Canonical repo map

12 repos exist under this account. Two are live. This file exists so that
question never has to be asked again.

## Live - touch these

| Repo | Visibility | Purpose |
|---|---|---|
| **sales-king-academy-complete** | private | **THE PLATFORM.** worker.js, wrangler.toml, deploy, backups, model + knowledge artifacts. Auto-deploys to Cloudflare on push to main. |
| **sales-king-academy** | public | **THE COMPUTE PLANE.** Scheduled compute, training, heartbeat. Unlimited Actions minutes. |

## Dormant - do not build on these

| Repo | Last push | Note |
|---|---|---|
| saleskingacademy | 2026-07-13 | TWA / Play Store pipeline (build-twa.sh, twa-manifest.json). Real, unfinished. |
| SalesKingAI | 2026-07-09 | **ARCHIVED.** Original Chain256 spec + docs. Its two genesis constants are WRONG (12:34:56.78 and 03:16:31.16). Production is midnight 2018-07-01. Do not port them back. |
| ska-tsi-core | 2026-03-31 | 26.7MB, worker.js snapshot from March. Superseded. |
| Sales-King-Academy- | 2026-03-24 | 1 stale workflow |
| SalesKing-Monorepo | 2025-10-08 | 1 stale workflow |
| sales | 2025-05-12 | **5 stale workflows** |
| skawebsite / skagi-core / ska-25-ai-master-system / Kai-deployment | - | empty or superseded |

## Rules

1. Platform code changes -> **sales-king-academy-complete** only.
2. Anything needing more than 10ms CPU -> **sales-king-academy**.
3. Anything touching user data stays **private**, always.
4. Stale public repos with workflows (`sales`, `SalesKing-Monorepo`,
   `Sales-King-Academy-`) should have Actions disabled so they cannot fire or
   confuse a search.

## Facts that are easy to get wrong

- Beats genesis is **1530403200** = 2018-07-01T00:00:00Z, **midnight**.
- Chain64 is never modified. Chain256 is strictly additive.
- Every Cloudflare deploy must declare all 14 bindings or they are silently
  dropped.
- Workers Free: 10ms CPU/request, 10ms CPU/cron, 1-minute cron floor,
  100k requests/day, 5 cron triggers, 1s startup budget.
