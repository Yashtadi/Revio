# Revio — AI Code Review for GitHub Pull Requests

> Revio reviews your pull requests the way a good teammate would — with the rest of the codebase in mind — and leaves clear, inline comments automatically.

---

## What is Revio?

When you open a pull request, Revio automatically reviews it and leaves inline comments — like a reviewer who read the whole file, not just the changed lines.

What makes it different: most review bots look at a diff on its own and miss context that lives elsewhere in the repo — your existing conventions, a helper function two files over, the code your change actually affects. Revio pulls in that related code before it reviews, so its feedback fits how your project is actually written.

## How it works

1. You open a pull request. GitHub notifies Revio through a signed webhook.
2. Revio confirms the message really came from GitHub, drops the job onto a queue, and immediately replies "got it."
3. A background worker picks up the job, fetches the changed code, and finds related code from the repository.
4. It asks an LLM to review the change, using that related code as context.
5. It posts the review as inline comments on the pull request.


<img width="900" height="872" alt="Screenshot 2026-07-06 110830" src="https://github.com/user-attachments/assets/bcfe22de-ad31-4b8c-a5c7-28ee00781a68" />

Why the two halves? GitHub expects a reply within about 10 seconds, but a good review takes longer than that. So Revio answers instantly (the API) and does the slow work separately (the worker). If it tried to review inside that 10-second window, it would drop requests.

## Tech stack

| Layer | Choice |
|---|---|
| API | Python, FastAPI |
| Background work | Redis queue + worker |
| Storage & search | PostgreSQL with the pgvector extension |
| Review model | LLM with structured, validated output |
| GitHub integration | GitHub App — webhooks + GitHub REST API |
| Packaging & delivery | Docker Compose, GitHub Actions (CI/CD), GitHub Container Registry |
| Observability | Structured logging, health checks, Sentry |

## Why it's built this way

A few decisions shape the whole system. Each one is a plain trade-off:

- **Reviews run in the background, not on the spot.** GitHub's 10-second limit forces this. Revio queues the job and replies immediately; a worker does the review afterward. Doing it inline would be simpler to write but would fail under any real load.
- **Duplicate events are ignored.** GitHub sometimes sends the same event twice. Every event has a unique ID, and Revio remembers IDs it has already handled — so a pull request never gets reviewed twice. Jobs that fail are retried with a growing delay between attempts.
- **Related code is searched, not stuffed in whole.** Revio keeps a searchable index of the repository (code turned into vectors in pgvector). For each PR it fetches only the most relevant pieces and feeds those to the model. Sending the entire repo every time would be far too large and expensive; searching keeps it focused and cheap.
- **The model's output is forced into a fixed shape.** LLMs can ramble or return messy text. Revio makes the model answer in a defined structure and validates it before posting, so every comment maps to a specific line in the diff instead of arriving as a wall of prose.

- **Code is chunked along function and class boundaries, not fixed-size windows.** A fixed-size cut can slice a function in half, so the retrieved context reads like a fragment instead of a coherent piece of code. Chunking on syntax boundaries keeps each retrieved piece meaningful on its own.

- **Deploys happen automatically on merge, not by hand.** Once tests pass, the pipeline builds a versioned image and pushes it to the running host itself — removing the "forgot to deploy" gap between merging code and it actually being live. Each image is tagged with its commit SHA, so rolling back is just redeploying the previous tag.

## Data model

A short tour of the main tables:

| Table | What it holds |
|---|---|
| `installations` | GitHub App installs and their access tokens |
| `repositories` | Repos Revio is watching |
| `code_chunks` | Repo code split into pieces, each with its vector embedding (used for search) |
| `reviews` | One row per PR reviewed — status, timing, and the posted comments |
| `jobs` | Queued review work, with state and retry count (for duplicate/failure handling) |

## API surface

| Endpoint | Purpose |
|---|---|
| `POST /webhooks/github` | Receives pull request events; verifies the signature before doing anything |
| `GET /health` | Liveness and readiness check for deployment |

## Quick start

Goal: from clone to a running instance in a few minutes.

```bash
# 1. Clone
git clone https://github.com/<your-username>/revio.git
cd revio

# 2. Add your settings (GitHub App credentials, LLM API key, database and Redis URLs)
cp .env.example .env

# 3. Start everything (API, worker, PostgreSQL, Redis)
docker compose up --build
```

Then register a GitHub App and point its webhook at your running instance so Revio starts receiving pull request events.

## Deployment

A short pre-release checklist:

- [ ] CI is green (lint and tests passing)
- [ ] Database migrations applied
- [ ] Environment variables set on the host (secrets, DB/Redis URLs, model key)
- [ ] GitHub App webhook URL points at the live instance
- [ ] CI/CD pipeline building and deploying on merge to `main`
- [ ] Smoke test: open a test PR and confirm a review is posted
- [ ] Rollback plan: redeploy the previous image if error rates spike

## CI/CD pipeline
On every push, GitHub Actions lints and runs tests. On merge to main, it also builds a Docker image tagged with the commit SHA, pushes it to GitHub Container Registry, and deploys it to the live host. If something goes wrong after a deploy, rolling back means redeploying the previous SHA — no rebuild needed.

## Roadmap

- [ ] Core loop — webhook → fetch changes → single review → post comment
- [ ] Deploy on a live host with Docker Compose
- [ ] Redis queue + worker; instant reply, background review
- [ ] Duplicate protection and retries with backoff
- [ ] Structured, validated output posted as inline comments
- [ ] Repository indexing — chunk code along function/class boundaries, embed, store in pgvector
- [ ] Incremental re-indexing (only changed files) on each push
- [ ] Context-aware reviews using search (RAG)
- [ ] Evaluation: compare review quality and speed, with vs. without context
- [ ] CI/CD pipeline — lint, test, build versioned image, deploy on merge to main
- [ ] Observability: structured logging, health checks, Sentry
- [ ] *(Stretch)* Split the reviewer into focused agents (security, architecture, summary)

## Project status

Revio is **in active development**, built in the open. The design above is settled; features are landing against the roadmap. Issues and feedback are welcome.
