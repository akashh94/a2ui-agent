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
  Row, Column, Card).

A separate repo, **a2ui-client**, holds the **demo web page** ("client") that
talks to this agent and **renders the UIs the agent generates**. It is
deployed to its own Cloud Run service and points at this agent's URL.

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
| `https://<agent-url>/catalog.json` | The catalog (the list of allowed UI components) |
| `https://<agent-url>/.well-known/agent-card.json` | The agent's "business card" (what it can do) |
| `https://<agent-url>/a2a/a2ui_agent` | The agent's A2A API (send it a message) |

The demo client page is a **separate repo** (`a2ui-client`), deployed to its
own Cloud Run service; point it at the agent with `?agent=<agent-url>`.

## Repository layout (top level)

```
a2ui-agent/     this repo: the deployable agent service
├── a2ui-agent/     the Cloud Run service (Python app + catalog)
│   └── app/        the service code + catalog
├── docs/           these documents
└── README.md       quick start

a2ui-client/    SEPARATE repo: the demo browser page (static HTML/JS),
                deployed to its own Cloud Run service
```
