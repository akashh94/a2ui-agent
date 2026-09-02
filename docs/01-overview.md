# 01 — Overview (plain language)

## What is this?

This is a small project that lets an **AI agent draw user interfaces for you**.

Instead of the agent just replying with text ("here is a button"), it can reply
with a **structured description of a UI** ("create a screen with a column;
inside it a heading, some text, and a button labelled Click Me"). A web page
then **renders that description** as real, clickable HTML.

It is like the difference between:

- a chef **telling you a recipe** (text), and
- a chef **sending a blueprint of a dish** to a kitchen that can cook exactly
  that dish (structured message → rendered UI).

The "blueprint" format is called **A2UI**. The "kitchen" is the client page.
The agent is the chef.

## An analogy for the whole system

Think of a **restaurant reservation system**:

- **The agent** = a host who knows the menu and can take your order.
- **The menu** = the **catalog**: "we only serve these 5 dishes" (Text,
  Button, Row, Column, Card). The host can never serve something not on the
  menu.
- **The kitchen** = the **client renderer**: it knows how to actually cook
  (render) each dish on the menu.
- **The A2A protocol** = the phone line / order slip format both sides agree
  on.
- **The agent card** = the restaurant's sign out front: "We speak A2A v0.9 and
  we support this menu."

When you (the user) ask the host for "a nice table for two", the host writes
an order slip (an A2UI message) using only menu items, hands it to the
kitchen, and the kitchen plates it up (renders the UI).

## The two kinds of requests

The agent has two behaviors, chosen automatically:

1. **Plain questions** — "What is the capital of France?"
   The agent uses a web-search tool and answers in **text**.
   (In the analogy: you asked a general question, not for food.)

2. **UI requests** — "Show me a demo with a button and some text."
   The agent **builds an A2UI message list** describing a screen, using only
   catalog components, and hands it back. The client renders it.
   (In the analogy: you ordered from the menu.)

How does the agent know which to do? Two "gates":

- **Gate 1 (the client decides):** the web page that talks to the agent
  declares "I can render A2UI" by attaching an **extension** to its message.
  No extension → the agent knows there is no kitchen, so it replies in text.
- **Gate 2 (the model decides):** even when A2UI is on, the agent's
  instructions say "only build a UI when the user asks for UI; otherwise just
  chat."

## Where does the AI live, and how is it reached?

The agent runs on **Cloud Run** (Google's serverless container platform) inside
a FastAPI web service. It listens for **A2A JSON-RPC** messages at
`/a2a/a2ui_agent`. Under the hood, the agent is built with **Google ADK**
(Agent Development Kit) and calls **Gemini** through **Vertex AI**.

The whole thing is **stateless-ish** (sessions are in-memory per server
instance), public (no login), and meant as a demo of the A2A + A2UI flow.

## What you should take away

- There is an **agent** (AI) that can answer text questions or generate UI
  descriptions.
- There is a **catalog** = the whitelist of UI components the agent may use.
- There is a **client** (a browser page) that can render those components.
- They talk over **A2A** (the protocol) using **A2UI** (the UI-message
  format), and they agree on the catalog through the **agent card**.
- The magic that stops the agent from inventing random components is: the
  catalog schema is fed to the model, and the model's output is **validated
  against that schema** before it is sent to the client.

Next: [02-architecture.md](02-architecture.md) — the actual pieces and files.
