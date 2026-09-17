# Sales King Academy - Compute Plane

**This repo is the PUBLIC compute plane. It is not the platform.**

Cloudflare Workers Free gives 10ms CPU per request AND per cron trigger, and
Cron Triggers cannot fire faster than once per minute. This repo is where work
that does not fit those limits runs: training, precompute, the solver cascade,
corpus generation, and the second-level heartbeat.

It is public for one reason: **Actions minutes are unlimited on public repos
and capped at 2,000/month on private ones.** Measured burn on the private repo
was ~4,092 min/month - which is why every workflow died for the last week of
July and again of August, then resurrected on the 1st.

## What lives here

- Scheduled compute: compute plane, search, knowledge accelerator, precompute
- Model work: tokenizer training, n-gram weighting, self-teach
- Heartbeat: second-level Python beat driver (Cloudflare's floor is 60s)

## What does NOT live here

| Stays private | Reason |
|---|---|
| `worker.js` | the platform itself |
| `deploy.yml` | needs worker source; auto-deploys to Cloudflare |
| `backup-d1.yml` | writes DB dumps to release assets - **user data** |
| anything touching `ska-ledger` | users, beats, orders |

**Never move a workflow here that touches user data.** Release assets and
Actions logs on a public repo are world-readable, permanently.

## Secrets

Set in Settings > Secrets and variables > Actions. Scheduled and dispatch
events cannot be triggered by forks, so these are not reachable from outside
PRs. **Never add a `pull_request` or `pull_request_target` trigger to a
workflow that uses them.**

Required: `CF_ACCOUNT_ID`, `CF_API_TOKEN`, `CF_AI_TOKEN`, `TEMPORAL_DB_ID`,
`GEMINI_API_KEY`, `GH_MODELS_TOKEN`, `SKA_HEARTBEAT_KEY`.

## Related repos

`REPOS.md` is the canonical map. If you are unsure which repo to touch, that
file is the answer.
