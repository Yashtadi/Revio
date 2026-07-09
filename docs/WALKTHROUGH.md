# Revio — A Complete Beginner's Walkthrough

This document explains **everything** about the Revio codebase from scratch, assuming you know
almost no software engineering. It explains *what* we built, *why* we built it that way, and
*what every tool and term means*. By the end you should be able to picture the whole system in
your head — both what exists today and where it's headed.

> **How to read this:** Sections 1–2 give you the big picture. Section 3 explains every tool
> and word. Section 4 walks the actual files. Sections 5–7 cover how it runs, the daily
> workflow, and the roadmap. Section 8 is a glossary you can jump back to any time.

---

## Table of contents

1. [What is Revio?](#1-what-is-revio)
2. [The big-picture architecture](#2-the-big-picture-architecture)
3. [The technology stack — every tool explained](#3-the-technology-stack--every-tool-explained)
4. [The codebase, file by file](#4-the-codebase-file-by-file)
5. [How it runs (two ways)](#5-how-it-runs-two-ways)
6. [The development workflow](#6-the-development-workflow)
7. [Where we are on the roadmap](#7-where-we-are-on-the-roadmap)
8. [Glossary](#8-glossary)

---

## 1. What is Revio?

**Revio is a robot code reviewer for GitHub.** When a developer proposes a change to a codebase
(this proposal is called a **pull request**, or **PR**), Revio automatically reads the change and
leaves helpful comments on it — pointing out bugs, style issues, and improvements — just like a
human teammate reviewing your work.

**What makes Revio special:** most review bots only look at the lines that changed, in isolation.
Revio is smarter — before it reviews, it goes and finds *related code elsewhere in the same
project* (a helper function two files over, the existing conventions, the code your change
affects) and uses that as **context**. So its feedback fits how *your* project is actually
written, not generic advice.

**Why build it?** It's a portfolio/resume project that demonstrates a lot of real, in-demand
engineering skills at once: web APIs, background job processing, databases, AI/LLM integration,
search, containers, and automated deployment. Each of those is a talking point in a job interview.

---

## 2. The big-picture architecture

**"Architecture"** just means the shape of the system: what the pieces are and how they talk to
each other. Here is the full intended flow when someone opens a pull request:

```
   GitHub ──(1) signed webhook: "a PR was opened!"──▶  FastAPI (the API)
                                                          │
                                          (2) The API checks the message really
                                              came from GitHub, drops a "job" onto
                                              a queue, and replies "got it" in
                                              under 10 seconds.
                                                          │
                                                          ▼
                                                   Redis (the queue)
                                                          │
                                          (3) A separate Worker program is
                                              watching the queue and picks up
                                              the job.
                                                          ▼
                                                    Worker process
                                                          │
                                          (4) The worker fetches the changed code
                                              and searches for RELATED code from
                                              the repository.
                                                          ▼
                                            PostgreSQL + pgvector  ──▶ related code
                                            (the searchable code index)    chunks
                                                          │
                                          (5) It asks an LLM (an AI model, Claude)
                                              to review the change, giving it that
                                              related code as context.
                                                          ▼
                                                     LLM (Claude)
                                                          │
                                          (6) The worker posts the AI's review as
                                              inline comments, back on the PR.
                                                          ▼
                                                        GitHub
```

### Why is it split into two halves (an "API" and a "Worker")?

This is the single most important design decision, so it's worth understanding.

- GitHub sends its "a PR was opened" notification (a **webhook**) and expects a reply **within
  about 10 seconds**. If you don't reply in time, GitHub considers the delivery failed.
- But a *good* AI review takes much longer than 10 seconds (searching code, calling the AI,
  formatting comments).
- If we tried to do the whole review before replying, we'd blow past the 10-second limit and
  GitHub would mark our deliveries as failing.

**The solution:** split the work in two.
- The **API** does only the fast part: verify the message, write down "there's a job to do" onto
  a **queue**, and immediately reply "got it." This takes milliseconds.
- The **Worker** does the slow part *afterward*, on its own time, by reading jobs off the queue.

This "reply instantly, do the heavy work in the background" pattern is everywhere in professional
software. You now understand *why* it exists: an external system imposed a deadline we can't meet
inline.

### What exists **today** vs. what's **planned**

We're building this in small milestones. Right now, only the foundation is built:

| Piece | Status today |
|---|---|
| **FastAPI (API)** with a `/health` check | ✅ Built (this is our M0 skeleton) |
| **PostgreSQL + pgvector** container | ✅ Running (not used by code yet) |
| **Redis** container | ✅ Running (not used by code yet) |
| Everything containerized with **Docker Compose** | ✅ Built |
| Auto-formatting, linting, tests | ✅ Built |
| Webhook endpoint, signature check | ⬜ Coming (M1) |
| Queue + Worker | ⬜ Coming (M1) |
| AI review with the LLM | ⬜ Coming (M2) |
| Database tables, retries, de-duplication | ⬜ Coming (M3) |
| Deploy to a live server + full CI/CD | ⬜ Coming (M4) |
| Code indexing + context-aware (RAG) reviews | ⬜ Coming (M5–M6) |

So today the picture is much smaller — just the left edge of that diagram — but the skeleton is
real, runs in containers, and is tested. Everything else slots into this foundation.

---

## 3. The technology stack — every tool explained

Here is every tool we've introduced, in plain language: what it is, and why it's here.

### Language & project management

- **Python** — the programming language everything is written in. Chosen because it's beginner-
  friendly and dominant in AI/web work. We use version **3.12**.

- **Virtual environment (`.venv/`)** — a private, isolated copy of Python and its libraries that
  belongs to *this one project*. Without it, installing a library for Revio could clash with
  another project on your computer. The virtual environment keeps Revio's libraries sealed off in
  its own folder.

- **uv** — the tool that manages all of the above. It installs the right Python version, creates
  the virtual environment, installs libraries, and records exactly which versions were used. Think
  of it as the project's package manager and environment manager rolled into one fast tool.

- **`pyproject.toml`** — the project's **manifest** (its ID card and settings file). It lists
  which libraries the project needs and holds configuration for our tools. It's the human-edited
  source of truth.

- **Lockfile (`uv.lock`)** — an auto-generated file recording the **exact** version of every
  library (down to sub-dependencies) that uv resolved. This guarantees the project installs
  *identically* on your laptop, on a teammate's laptop, in Docker, and on the server. You never
  edit it by hand.

- **`.python-version`** — a tiny file naming the Python version this project uses (`3.12`), so uv
  and everyone else picks the same one.

### The web application

- **FastAPI** — the **framework** we use to build our web API. A "framework" is a pre-built
  toolkit that handles the boring, hard parts of web servers (parsing requests, routing URLs to
  functions, converting Python objects to JSON) so we only write the interesting logic. FastAPI is
  modern, fast, and gives us free interactive documentation.

- **API (Application Programming Interface)** — a way for programs to talk to each other over the
  web. Ours exposes URLs (called **endpoints**) like `/health`. When something sends a request to
  an endpoint, our code runs and sends back a response (usually **JSON**, a simple text format for
  structured data).

- **Endpoint** — a single URL your API responds to, paired with an action. `GET /health` is an
  endpoint: "when someone does a GET request to `/health`, run this function."

- **uvicorn** — the **server** that actually runs a FastAPI app and listens for incoming web
  requests. FastAPI *describes* how to respond; uvicorn *does the listening and talking*. (Under
  the hood it speaks a Python web standard called **ASGI** — you don't need to worry about that
  word beyond "it's how modern async Python web apps and servers connect.")

- **pydantic-settings** — a small library that reads **configuration** (settings like names, URLs,
  and secret keys) from **environment variables** and validates them. It's how the app will later
  load secrets (API keys, database URLs) without hardcoding them into the code.

- **Environment variable** — a named value that lives *outside* your code, in the operating
  system or environment the app runs in (e.g. `DATABASE_URL=...`). Used for anything that changes
  between your laptop and the server, and especially for **secrets** you must never write directly
  into code.

### Testing

- **pytest** — the tool that runs our **tests**. A test is a small piece of code that checks our
  real code does what we expect (e.g. "`/health` returns `{"status": "ok"}`"). If someone breaks
  it later, a test fails loudly instead of the bug sneaking into production.

- **httpx** — a library for making web requests from Python. FastAPI's test tool uses it under the
  hood to call our endpoints during tests without needing a real running server.

### Code quality

- **ruff** — two tools in one:
  - a **formatter**: rewrites our code into one consistent style automatically, so we never argue
    about spacing or import order and our diffs stay clean.
  - a **linter**: statically analyzes the code (reads it without running it) to catch likely bugs
    and bad patterns — unused imports, undefined names, and so on.

- **pre-commit** — a "gatekeeper" that runs checks (like ruff) **automatically every time you make
  a git commit**. If the checks fail, the commit is blocked. This makes it *impossible* to
  accidentally commit badly formatted or broken code. It's the enforcement layer; ruff is the
  worker it runs.

### Version control

- **git** — the tool that tracks the history of your code: every change, when, and by whom. It
  lets you save checkpoints (**commits**), undo, and collaborate.

- **commit** — a saved checkpoint of your code at a moment in time, with a message describing what
  changed.

- **GitHub** — a website that hosts git repositories online. It's where your code lives remotely,
  and (crucially for Revio) it's the system that will send us pull-request notifications.

- **push / pull** — **push** uploads your local commits to GitHub; **pull** downloads commits from
  GitHub to your machine.

- **merge conflict** — when two different edits change the same lines and git can't decide which to
  keep, so it asks you to choose. (We hit and resolved one in the README.)

### Containers & orchestration

- **Docker** — a tool that packages your app together with its *entire* environment (the right
  Python, the right libraries, system settings) into a portable unit, so it runs *identically*
  everywhere — your laptop, a teammate's machine, the production server. It cures the classic
  "but it works on my machine" problem.

- **Image** — a frozen, read-only snapshot built from a recipe: your code + Python + dependencies.
  Analogy: a *class* in programming, or a cookie cutter.

- **Container** — a running instance of an image. Analogy: an *object*, or a cookie made from the
  cutter. One image can spawn many containers.

- **`Dockerfile`** — the recipe for building *our app's* image, step by step (start from Python,
  install dependencies, copy code, define the start command).

- **`.dockerignore`** — like `.gitignore`, but for Docker: lists files to keep *out* of the image
  build (e.g. our Windows virtual environment, which must not leak into a Linux container).

- **Docker Compose** — a tool to define and run **several containers together** with one command
  (`docker compose up`). Revio's compose file runs three containers as one system: the API,
  PostgreSQL, and Redis, all on a shared private network so they can talk to each other by name.

- **Volume** — a persistent storage area Docker keeps *outside* a container, so data (like the
  database's contents) survives even when the container is stopped and recreated.

### The data & queue services

- **PostgreSQL ("Postgres")** — a powerful, popular **relational database**: software that stores
  structured data in tables (rows and columns) and lets you query it. Revio will use it to remember
  installations, repositories, past reviews, jobs, and the code index.

- **pgvector** — an *extension* (add-on) for PostgreSQL that lets it store and search **vectors**.
  A vector is a list of numbers that represents the *meaning* of a piece of text or code. Storing
  code as vectors is what enables "find related code" search later (this is the heart of **RAG**,
  explained in the glossary). We use the `pgvector/pgvector:pg16` image, which is Postgres 16 with
  pgvector already installed.

- **Redis** — a very fast in-memory data store. Revio uses it as the **queue**: the API writes
  "there's a job to do" into Redis, and the Worker reads jobs out of it. It's the hand-off point
  between the fast half and the slow half of the system.

### Delivery (coming in later milestones)

- **GitHub Actions** — GitHub's built-in automation. It will run our tests and linter on every
  push (**CI**), and later build and deploy the app automatically (**CD**).
- **CI/CD** — **Continuous Integration** (automatically test every change) and **Continuous
  Deployment** (automatically ship every approved change to the live server). The goal: no manual,
  error-prone steps between writing code and it being live.
- **GHCR (GitHub Container Registry)** — a place to store built Docker images, so the server can
  download and run them.

---

## 4. The codebase, file by file

Here's the current project structure, annotated:

```
Revio/
├─ app/                      ← our application's Python code (a "package")
│  ├─ __init__.py            ← empty; marks "app" as an importable package
│  ├─ config.py              ← loads settings from environment variables
│  └─ main.py                ← the FastAPI app + the /health endpoint
├─ tests/                    ← automated tests
│  └─ test_health.py         ← checks that /health works
├─ docs/
│  └─ WALKTHROUGH.md         ← this document
├─ .github/                  ← (coming in M0's CI step) GitHub Actions workflows
├─ Dockerfile               ← recipe to build our app's Docker image
├─ .dockerignore            ← files to keep out of the Docker build
├─ docker-compose.yml       ← runs api + postgres + redis together
├─ .env.example             ← template listing which settings to set
├─ .env                     ← your real local settings (git-ignored; never committed)
├─ .gitignore               ← files git should never track
├─ .pre-commit-config.yaml  ← which checks run automatically on each commit
├─ pyproject.toml           ← project manifest: dependencies + tool config
├─ uv.lock                  ← exact resolved versions (auto-generated)
├─ .python-version          ← pins Python 3.12
└─ README.md                ← the project's public overview / design doc
```

### `app/__init__.py`
An **empty** file. Its mere presence tells Python "the `app` folder is a *package*" — an
importable collection of code. This is why we can write `from app.config import settings`.

### `app/config.py`
Defines a `Settings` class using **pydantic-settings**. Each field (like `app_name`) is
automatically filled from an environment variable of the same name, or falls back to a default.
It reads a local `.env` file too. We create one shared `settings` object that the rest of the app
imports. This is the single, safe place all configuration and (later) secrets flow through.

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_name: str = "Revio"
    environment: str = "development"

settings = Settings()
```

### `app/main.py`
Creates the FastAPI **application object** (`app`) and defines the `/health` endpoint.

```python
from fastapi import FastAPI
from app.config import settings

app = FastAPI(title=settings.app_name)

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- `app = FastAPI(...)` is the application uvicorn serves.
- `@app.get("/health")` is a **decorator** — it registers the function beneath it as the handler
  for `GET /health`. When a request hits that URL, FastAPI runs `health()` and turns the returned
  dictionary into a JSON response: `{"status": "ok"}`.
- **Why a health endpoint?** It's the simplest "am I alive?" check. Docker, load balancers, and
  deployment tools ping it to confirm the service is up. It also proves, end to end, that the whole
  app boots and responds — which is exactly what our first milestone is about.

### `tests/test_health.py`
Uses FastAPI's `TestClient` (a fake browser) to call `/health` in-process and assert the response
is correct. Run with `uv run pytest`.

### `Dockerfile`
The recipe to build our app's image: start from a small Python 3.12 Linux image, copy in the uv
tool, install *only* the production dependencies (from the lockfile, for reproducibility), copy our
code, and set the start command to launch uvicorn on port 8000. Dependencies are installed *before*
copying code so Docker can cache that slow step and rebuild quickly after code edits.

### `docker-compose.yml`
Defines three services that start together:
- **`api`** — built from our `Dockerfile`; port 8000 is exposed to your machine.
- **`db`** — PostgreSQL 16 + pgvector, with a persistent volume for its data.
- **`redis`** — the queue's backing store.

They share a private network, so later the API and Worker can reach the database at the hostname
`db` and Redis at `redis` — Compose provides that name resolution automatically.

### The config/dotfiles
- **`.env.example`** (committed) is the template; **`.env`** (git-ignored) holds your real local
  values. You created `.env` by copying the example.
- **`.gitignore`** keeps junk and secrets out of git. **`.dockerignore`** keeps them out of Docker
  builds. **`.pre-commit-config.yaml`** lists the automatic pre-commit checks. **`pyproject.toml`**
  + **`uv.lock`** + **`.python-version`** define the project and pin everything.

---

## 5. How it runs (two ways)

There are two ways to run Revio during development, and it's useful to understand both.

### A) Directly with uv (fast, for quick iteration)
```
uv run uvicorn app.main:app --reload
```
uv activates the project's virtual environment and starts uvicorn. `--reload` restarts on file
changes. Good for rapid coding. Only runs the API — no database/redis.

### B) With Docker Compose (the full stack, like production)
```
docker compose up --build
```
Builds the app image and starts all three containers (api + db + redis) together, mimicking how it
will run on the server. This is the realistic environment.

### What happens when you visit `GET /health`
1. Your browser sends an HTTP `GET` request to `http://localhost:8000/health`.
2. uvicorn (the server) receives it and hands it to FastAPI.
3. FastAPI matches the URL `/health` to the `health()` function and calls it.
4. `health()` returns the Python dict `{"status": "ok"}`.
5. FastAPI converts that dict to JSON and uvicorn sends it back.
6. Your browser displays `{"status":"ok"}`.

That's the entire request lifecycle. Every future endpoint (like the webhook receiver) follows the
same path — just with more logic in the middle.

---

## 6. The development workflow

The day-to-day loop you'll repeat for every change:

1. **Edit** code in `app/` (or tests in `tests/`).
2. **Run it** locally (`uv run uvicorn ...`) and/or **test it** (`uv run pytest`).
3. **Format & lint** (ruff — also runs automatically at commit time).
4. **Commit** the change with git (pre-commit checks run and must pass).
5. **Push** to GitHub.
6. **CI** (GitHub Actions — set up at the end of M0) re-runs the checks on GitHub's servers as a
   final gate nobody can skip.

The philosophy: **catch problems as early as possible.** Your editor catches typos; ruff catches
style/lint issues; pre-commit blocks bad commits locally; CI is the non-negotiable final gate. Same
checks, layered.

---

## 7. Where we are on the roadmap

The project is built in milestones (M0–M7). Each one ends with something that actually works and
can be demonstrated.

- **M0 — Skeleton (in progress / mostly done):** project setup, `/health` API, tests, tooling,
  Docker Compose with Postgres + Redis, and (next) automated CI. ← **we are here**
- **M1 — Webhook + queue + worker:** register a GitHub App; receive and verify PR webhooks; put a
  job on the Redis queue; a worker posts a placeholder comment. Proves the whole GitHub loop.
- **M2 — Real AI review:** send the PR's changes to the LLM (Claude), get a structured, validated
  set of findings, post them as inline comments.
- **M3 — Reliability:** database tables (via SQLAlchemy + Alembic), ignore duplicate events, retry
  failed jobs with backoff.
- **M4 — Deploy + full CI/CD:** ship the app to a live server automatically on every merge to
  `main`, with versioned images and easy rollback.
- **M5 — Code indexing:** split the repo's code into meaningful chunks, turn them into vectors,
  store them in pgvector; re-index only changed files on each push.
- **M6 — Context-aware (RAG) reviews:** for each PR, search the index for related code and feed it
  to the LLM as context — the feature that makes Revio "read the whole codebase."
- **M7 — Observability + evaluation:** structured logs, error tracking (Sentry), readiness checks,
  and a way to measure review quality with vs. without context.
- **Stretch — Multiple specialized agents** (security, architecture, summary) that combine into one
  review.

---

## 8. Glossary

Quick definitions you can jump back to.

| Term | Meaning |
|---|---|
| **API** | A way for programs to talk over the web via URLs (endpoints) that return data (usually JSON). |
| **ASGI** | The modern Python standard that lets async web apps (FastAPI) and servers (uvicorn) connect. |
| **CI / CD** | Continuous Integration (auto-test every change) / Continuous Deployment (auto-ship every approved change). |
| **Commit** | A saved checkpoint of your code in git, with a message. |
| **Container** | A running instance of a Docker image. |
| **Decorator** | Python syntax (`@something`) that adds behavior to the function below it; FastAPI uses it to attach URLs to functions. |
| **Dependency** | An external library your project needs to run. |
| **Docker** | Packages an app + its environment into a portable unit that runs identically everywhere. |
| **Endpoint** | One URL + action your API responds to (e.g. `GET /health`). |
| **Environment variable** | A configuration value stored outside the code, in the environment; used for settings and secrets. |
| **FastAPI** | The web framework Revio's API is built with. |
| **Framework** | A pre-built toolkit that handles the hard, repetitive parts of a kind of program. |
| **git** | Version-control tool that tracks your code's history. |
| **GitHub** | Website hosting git repositories; also the source of Revio's PR notifications. |
| **Image** | A frozen, read-only snapshot used to create containers. |
| **JSON** | A simple text format for structured data (used in API responses). |
| **Linter** | A tool that reads code (without running it) to flag likely bugs and bad patterns. |
| **Lockfile** | Auto-generated record of exact dependency versions, for reproducible installs. |
| **LLM (Large Language Model)** | The AI model (Claude) that writes the actual reviews. |
| **pgvector** | A PostgreSQL add-on for storing and searching vectors. |
| **PostgreSQL** | A relational database that stores structured data in tables. |
| **Pull request (PR)** | A proposed change to a codebase on GitHub — what Revio reviews. |
| **pydantic-settings** | Library that loads and validates settings from environment variables. |
| **Queue** | A waiting line of jobs; the API adds to it, the worker takes from it (Revio uses Redis for this). |
| **RAG (Retrieval-Augmented Generation)** | Technique of *searching* for relevant information and feeding it to an AI as context, instead of relying on the AI's memory alone. Revio uses it to give the LLM related code. |
| **Redis** | A very fast in-memory data store; Revio uses it as the job queue. |
| **Repository ("repo")** | A project's folder tracked by git/GitHub. |
| **ruff** | Fast tool that formats and lints Python code. |
| **uv** | Tool that manages Python versions, virtual environments, and dependencies. |
| **uvicorn** | The server that runs the FastAPI app and handles web requests. |
| **Vector** | A list of numbers representing the *meaning* of text/code, enabling similarity search. |
| **Virtual environment** | An isolated per-project Python + libraries folder (`.venv/`). |
| **Volume** | Docker's persistent storage that outlives a container (e.g. the database's data). |
| **Webhook** | An automatic HTTP message one system sends another when an event happens (GitHub → Revio when a PR opens). |
| **Worker** | A separate program that processes jobs from the queue (does the slow review work). |

---

*This document grows with the project. As we build M1, M2, and beyond, new sections and terms will
be added here so it always reflects the whole system.*







// Random line change to test webhook setup 
// test 1 failed so making another commit to test again

