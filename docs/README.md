# a2ui-agent — Beginner Documentation

Everything you need to understand this project, from zero. Read these in order
if you are new:

| Doc | What it covers |
|---|---|
| [01-overview.md](01-overview.md) | What this project is, in plain language, with an analogy |
| [02-architecture.md](02-architecture.md) | The pieces (agent, catalog, client, server) and how they fit |
| [03-flow.md](03-flow.md) | The exact step-by-step journey of one user request (both paths) |
| [04-catalog.md](04-catalog.md) | What the catalog is, how custom components work, how the agent is constrained to it |
| [05-glossary.md](05-glossary.md) | A2A / A2UI / ADK / catalog terms explained simply |
| [06-troubleshooting.md](06-troubleshooting.md) | Common errors, "why is this failing", and fixes |

## The shortest possible summary

This repo runs **one Cloud Run service** that contains:

- an **AI agent** (Google's ADK framework + Gemini) that can answer questions,
  and
- a **catalog** describing a small set of UI building blocks (Text, Button,
  Row, Column, Card), and
- a **demo web page** (the "client") that talks to the agent and **renders
  UIs the agent generates**.

The whole point: a user says "show me a demo with a button and text", the
agent **builds a UI description in a standard format called A2UI**, and the
client page **turns that description into real clickable UI** — using only the
components the catalog allows.

The communication between the client and the agent follows the official
**A2A (Agent-to-Agent)** and **A2UI** specifications, so any conforming client
or agent can interoperate.

## Live endpoints

| Endpoint | Purpose |
|---|---|
| `https://<service-url>/catalog.json` | The catalog (the list of allowed UI components) |
| `https://<service-url>/.well-known/agent-card.json` | The agent's "business card" (what it can do) |
| `https://<service-url>/a2a/a2ui_agent` | The agent's A2A API (send it a message) |
| `https://<service-url>/client` | The demo client page (open in a browser) |

## Repository layout (top level)

```
a2ui-agent/     the whole project (this repo)
├── a2ui-agent/     the deployable service (the thing on Cloud Run)
│   ├── app/        the Python service code + catalog
│   ├── client/     the demo browser page (static HTML/JS)
│   └── *.sh        build/deploy scripts
├── a2ui-server/    (legacy) the OLD architecture — no longer used
├── docs/           these documents
├── README.md       quick start
└── SESSION_HANDOFF.md  session notes (project history)
```

> Tip: ignore the `a2ui-server/` folder unless you are reading history. It was
> the previous design (a catalog + chat proxy in front of a Vertex AI Agent
> Engine). The new design is one self-contained A2A service.
