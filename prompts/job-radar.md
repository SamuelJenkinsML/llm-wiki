Run the JOB RADAR operation. Produce today's ranked shortlist of roles worth applying to.

Read `vault-config.md` first for the vault path and conventions. All output goes in
`_llm/` — never create machine-generated pages elsewhere in the vault.

## 0. Establish the date

Run `date +%Y-%m-%d`. Never infer the date from anything else. Call it `{today}`.

## 1. Load the profile — the vault is the source of truth

Read `Interviews/Staff Role Roadmap 2026-2027.md` in the vault. Its **gap analysis**,
**Q1–Q4 objectives**, **decision gate** and **CV retranslation** section are the
authoritative ranking criteria. Rank against what that file says today, not against what
you remember.

If that file is missing or unreadable, fall back to the summary below and say in the
output that you used the fallback:

> UK-based, UK work authorisation, no sponsorship needed. ~10 years engineering, ~7
> building and leading ML/AI platforms. Route in: chemical engineering → nuclear
> simulation → industrial IoT → ML platform lead.
>
> **Tripadvisor (current)** — ML Platform technical lead: 70+ data scientists and MLEs,
> ~100 models in production, 30–35k RPS peak, technical lead on the Ray consolidation
> across serving/training/batch, Ray Summit 2025 speaker, LLM on-call agent in
> production (PagerDuty → LangGraph multi-agent → Ray Serve → Bedrock → AgentGateway →
> Arize Phoenix for evals).
> **Ultraleap** — MLOps lead, 2.5 years, ~20 MLEs, 70% experiment-throughput uplift,
> hand-tracking inference <5ms p50 across 80+ hardware platforms.
> **Malvern Panalytical** — industrial IoT, Microsoft smart manufacturing design award.
>
> Depth: Python, Go, Rust; Kubernetes at scale (6 EKS clusters, production on-call);
> custom Go controllers for GPU autoscaling; spot-interruption handling with Istio
> connection draining; AWS/Azure/GCP, ArgoCD, Istio, Ray. Measured impact: 45%
> utilisation lift; ~35% cloud cost reduction; −40% cost per generated frame; >100ms p90
> latency reduction on semantic search.
>
> Honest gaps — do not dress these up: operates inference platforms but has **not built
> inference internals** (kernels, CUDA, custom serving runtimes); scale is
> **many-small-models**, not few-enormous-models; no TPU/Trainium/Inferentia; no public
> Rust; weak on TypeScript and frontend.
>
> Direction of travel: deliberately repositioning as an **LLM inference systems
> engineer**, while **MLOps / ML platform roles remain a first-class target** in their
> own right — that is the current depth, not a consolation prize. On a tie between two
> otherwise equal roles, prefer the one that builds inference-internals credibility.

Then read, if they exist:

- the two most recent files in `_llm/job-radar/` — this is your no-repeat memory
- `_llm/status/job-radar.md` — the seen ledger and ATS coverage

These are your only memory of previous runs. If neither exists, this is the first run.

## 2. What counts as a match

**Titles — search broadly, titles vary wildly.** At minimum: AI Infrastructure Engineer;
ML Platform Engineer; MLOps Engineer; Inference Engineer; Inference Platform Engineer;
Software Engineer (Infrastructure / Systems / Platform); Distributed Systems Engineer;
Performance Engineer; GPU / Accelerator Infrastructure; Compute Platform; Training
Infrastructure; Model Serving; SRE (ML); Research Engineer (Systems); Member of Technical
Staff (Infrastructure).

**Seniority.** Principal, Staff, Distinguished, Lead, Senior Staff strongly preferred.
Senior is acceptable where the role itself is strong — frontier lab, genuine
inference-internals work, unusual scope, or a well-scoped senior MLOps/ML-platform role
at a serious engineering organisation. Never surface mid or junior roles. A *Senior*
title is a note in **The catch**, not grounds for exclusion.

**Location — hard filter.** UK-based, or remote roles that explicitly hire in the UK.
Three acceptable shapes — a role qualifies if it fits **any one** of them:

- **Remote** (UK-eligible). Ideal; occasional travel is fine.
- **London** — **maximum 2 days per week** in office. Reject 3+ days/week and
  London-office-mandatory full-time.
- **Manchester area** — **onsite is fine, including 5 days a week in office.** The
  2-day cap is a London-commute constraint and does **not** apply here. Read this as
  Greater Manchester and its reasonable commuter neighbours (Salford, Stockport,
  Trafford, Bolton, Warrington, Wilmslow). A full-time Manchester office role is a
  genuine match — do not downrank it for being onsite.

Reject anything that cannot employ a UK resident. Discard US-only remote — it does not
satisfy UK employment. If the office policy is not stated, say so explicitly — do not
assume remote.

**Sectors.** Emphasise but do not restrict to: frontier AI labs; AI infrastructure and
inference companies; biotech, life sciences, computational drug discovery; scientific
computing. **For MLOps / ML-platform roles the sector net is wider** — any organisation
running ML at real scale qualifies (fintech, retail, media, telco, consultancy,
public sector), and Manchester-area employers in particular should be searched on this
basis rather than only for AI-lab work. Genuinely interesting roles outside these are
welcome — say why.

**Compensation — read this carefully, it overrides any figure you find elsewhere.**
The floor is **£100k**. Anything at or above £100k is worth considering; more is
better, and comp is one input among several, never the headline. Do **not** anchor on
frontier-lab or US pay bands, do **not** benchmark roles against Anthropic or any other
lab's compensation, and do **not** describe a role as weak, disappointing or
"below target" because it pays under £200k, £300k or any similar figure. A £120k
Manchester MLOps role and a £350k London inference role are both legitimate results;
rank them on fit, scope and career direction, not on the gap between their salaries.
If the roadmap file in the vault states a target band, treat it as aspiration, not as a
filter — this floor governs. Flag comp only when it is **below £100k** (reject), or
when it is genuinely notable. Most postings disclose nothing; "not disclosed" is a
neutral fact, not a mark against the role.

**Exclusions.** Tripadvisor (current employer — never recommend). Recruitment agencies
and job aggregators: go to the company's own ATS or careers page as the source of truth.
Anything you cannot verify is live.

## 3. The Anthropic hold — do not break this

`Interviews/Staff Role Roadmap 2026-2027.md` records a deliberate strategy: the single
Anthropic application is unspent, held until **Q4 2027 (target Jun 2027)**, with a
personal decision gate on **Fri 27 Nov 2026**. The note says *"Do not apply early to test
the water."*

Therefore **Anthropic roles never appear in the top five.** Put them in a separate
`## Watching — do not apply yet` section with a one-line reason. This is intel, not a
recommendation.

## 4. Deterministic harvest — company ATS APIs

Query these public, unauthenticated endpoints with `curl`:

- Greenhouse: `https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=false`
- Ashby: `https://api.ashbyhq.com/posting-api/job-board/{token}`
- Lever: `https://api.lever.co/v0/postings/{token}?mode=json`

**Pacing is critical.** These endpoints rate-limit aggressively. `sleep 2` between calls.
On a non-200 or empty body, wait 5s and retry **once** before treating a token as dead.
An unpaced loop fails every request and silently produces an empty report — which looks
exactly like a quiet market. Do not let that happen.

Known-good tokens (verified 2026-08-23 — re-validate, boards move):

- Greenhouse: `anthropic`, `isomorphiclabs`, `wayve`, `stabilityai`, `deepmind`
  (the `deepmind` board is incomplete — cross-check DeepMind with WebSearch, not by
  scraping Google's careers portal; see the fetch discipline in step 5)
- Ashby: `openai`, `elevenlabs`

Also try, and keep whatever resolves: Mistral, Cohere, Poolside, Synthesia, Nscale,
Cursor, Sierra, Harvey, Perplexity, Scale AI, Together AI, Modal, Baseten, Fireworks AI,
Groq, Cerebras, Graphcore, Recursion, Insilico Medicine, BenevolentAI, Genomics England,
Wellcome Sanger Institute, EMBL-EBI, Oxford Nanopore, Relation Therapeutics, Latent Labs,
CHARM Therapeutics, Iambic Therapeutics, Cradle Bio, Basecamp Research.

Filter to locations containing London / **Manchester** / UK / United Kingdom / Remote
(Europe, UK, Global). Include Greater Manchester spellings and neighbours (Salford,
Stockport, Trafford, Bolton, Warrington, Wilmslow).

## 5. Discovery harvest — web search

Run WebSearch across title synonyms × seniority × location, where location spans
**UK-remote, London, and Manchester**. Look for roles posted or updated in the
**last 14 days**. Cover the AI-lab side, the biotech/life-sciences side, *and* the
broader MLOps/ML-platform market — do not let one dominate. Spend at least a few
queries explicitly on **Manchester and the North West**, which the London-centric
ATS list above will otherwise miss entirely.

**Discovery is WebSearch's job, not WebFetch's.** WebSearch runs server-side. Every
`curl` and `WebFetch` in this run goes out from a home broadband IP — the same IP used
to apply for these jobs. So find roles by searching, and spend fetches only on postings
you are about to verify.

### Fetch discipline — binds every step, including verification

- **ATS APIs are unmetered.** Poll Greenhouse, Ashby and Lever freely, subject to the
  step 4 pacing rule. They are public endpoints built to be polled by third parties.
- **First-party careers pages: 6 fetches per run, maximum.** Spend them where coverage
  is weakest — the "no ATS path found" list in `_llm/status/job-radar.md` exists for
  this. Rotate across runs; do not fetch the same six every night.
- **A host that returns 403, 429, or a bot/CAPTCHA interstitial is finished for the
  run.** Do not retry it and do not try a second URL on that host. The step 4
  retry-once rule covers ATS tokens only and does not extend here.
- **Google-owned properties: search, never scrape — one fetch per run, maximum.**
  Discover Google and DeepMind roles through WebSearch. You may spend a single
  `google.com/about/careers` fetch per run, and only to verify a role that is about to
  enter today's five under step 6. Never fetch to browse the portal, to enumerate it, or
  to re-check a ledger role you are not publishing today. If that budget is spent or the
  fetch fails, the role goes unpublished — say so in Coverage rather than publishing it
  unverified. Nightly scraping of Google's careers portal trips its anti-automation and
  puts CAPTCHAs on a shared household IP; the coverage it buys does not justify that.

## 6. Verify — nothing unverified reaches the top five

WebFetch every candidate that might make the shortlist. Confirm: the posting is **live**;
the **location and office policy**; the **seniority**; **comp if stated**; the **direct
application URL**.

Verification against ATS posting URLs (Greenhouse, Ashby, Lever) is unmetered — verify as
many candidates as you need. The step 5 fetch discipline still binds: a blocked host stays
blocked for the run, and a Google careers URL comes out of the one-fetch budget.

**Never invent, infer or extrapolate a role.** If verification fails, drop it. If fewer
than five qualify today, **publish fewer and say so plainly** — a short honest list is
the correct output on a quiet day. Padding destroys the tool's value.

## 7. Rank, then apply the no-repeat rule

Score each verified role against the profile from step 1. Then:

- **Exclude anything that was in yesterday's top five**, unless the posting has
  *materially changed* — reposted, updated date, new req ID, changed scope. If so it may
  return, marked `repost`, with a note on what changed.
- A role dropped two or more days ago may return freely. The rule is only about
  consecutive days.
- Cross-check the seen ledger in `_llm/status/job-radar.md` so you can say how long a
  role has been open and whether it has appeared before.

## 8. Write `_llm/job-radar/{today}.md`

```markdown
---
type: llm-generated
generated: {today}
---
# Job Radar — {Weekday D Month YYYY}

## Today's Five

### 1. {Company} — {Role title}
- **Fit** {n}/100 — one-line justification
- **Location** {location + office policy} — which of the three shapes it clears
  (remote / ≤2 days London / Manchester-area onsite)
- **Comp** {if disclosed, stated neutrally; flag only if below the £100k floor}
- **Why this suits you** — 2–3 sentences grounded in the roadmap's own facts
- **The catch** — what you would be stretching on, honestly
- **The angle** — which specific project to lead with
- **Apply** {direct URL}

## Watching — do not apply yet
Anthropic and any other held roles, each with the reason.

## Market notes
2–3 sentences on what moved: new openings, sectors heating or cooling, patterns worth knowing.

## Sources checked
Which ATS boards resolved, which failed, how many postings were seen before filtering.
```

Use `[[wikilinks]]`, never markdown links, for anything inside the vault. Follow the
vault's two link idioms: bare filename for root-level notes
(`[[Staff Role Roadmap 2026-2027]]`), full vault path with a pipe alias for nested ones
(`[[_llm/job-radar/2026-08-24|Sunday's radar]]`). Link to
`[[Staff Role Roadmap 2026-2027]]` wherever a role speaks to a specific Q1–Q4 objective
or closes a named gap. Application URLs stay as plain external markdown links.

## 9. Update `_llm/status/job-radar.md`

Overwrite it each run. Same frontmatter (`type: llm-generated`, `generated: {today}`).
Contents:

- Today's five as a compact table — company, role, fit, and a link to today's note.
- `## Seen ledger` — every role surfaced in the last 30 days:
  `company · title · first seen · times surfaced · last surfaced · status`.
  Prune entries older than 30 days.
- `## Coverage` — which ATS tokens are alive and which have gone dead, so a dead token
  gets noticed rather than silently shrinking the search. List separately any host that
  returned 403, 429 or a CAPTCHA as **blocked** — that is not the same as a dead (404)
  token, and it is the signal that this job is fetching something it should be searching.

Do not edit `Interviews/Job Radar.md` — that hub note is user-owned and transcludes this
file.

## 10. Log

Append one line to `_llm/log.md` in the existing format: date, `job-radar`, how many
roles were surfaced, how many boards were checked, and anything that failed.

## Tone

Write like a well-informed friend who knows the background and is not selling anything.
Second person, direct, opinionated. Bold the single most actionable line. Be blunt about
weak matches and about roles that look good but are not. If the market is thin today, say
so — do not manufacture enthusiasm.
