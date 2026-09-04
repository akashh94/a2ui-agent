# 04 — The catalog and custom components

## What a catalog is

A **catalog** is a JSON Schema document that says:

> "These are the UI components an agent is allowed to build with, and here is
> exactly what each one looks like (its properties, which are required)."

It is the **whitelist / contract** between the agent and the client:

- The **agent** is told (in its prompt) *and* constrained (by validation) to
  use only these components.
- The **client** registers a real renderer (HTML/JS/etc.) for each component
  name, under the catalog's `catalogId`.
- A UI surface the agent creates carries a `catalogId`; the client only
  renders surfaces whose `catalogId` it registered. (No match → it cannot
  render that surface.)

In this repo, the catalog lives at `a2ui-agent/app/catalog.json` and is also
served at `GET /catalog.json` on the deployed service, so clients can fetch
and register it. Its `catalogId` is the URL of that endpoint:
`https://<APP_URL>/catalog.json`.

## Anatomy of `app/catalog.json`

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://<service>/catalog.json",
  "title": "A2UI Agent Demo Catalog",
  "description": "...",
  "catalogId": "https://<service>/catalog.json",

  "components": {
    "Text":   { ...component schema... },
    "Button": { ...component schema... },
    "Row":    { ...component schema... },
    "Column": { ...component schema... },
    "Card":   { ...component schema... }
  },

  "$defs": {
    "CatalogComponentCommon": { "type": "object", "properties": { "weight": { ... } } },
    "anyComponent": {
      "oneOf": [
        { "$ref": "#/components/Button" },
        { "$ref": "#/components/Card" },
        { "$ref": "#/components/Column" },
        { "$ref": "#/components/Row" },
        { "$ref": "#/components/Text" }
      ],
      "discriminator": { "propertyName": "component" }
    },
    "anyFunction": { "enum": ["none"] }
  }
}
```

### Reading a component schema

Each component is an object schema built from `allOf` (three parts merged):

```json
"Text": {
  "type": "object",
  "allOf": [
    { "$ref": "common_types.json#/$defs/ComponentCommon" },   // shared spec props (id etc.)
    { "$ref": "#/$defs/CatalogComponentCommon" },             // weight (layout)
    {
      "type": "object",
      "properties": {
        "component": { "const": "Text" },                     // the discriminator
        "text": { "$ref": "common_types.json#/$defs/DynamicString", "description": "..." },
        "variant": { "type": "string", "enum": ["h1","h2","h3","h4","h5","caption","body"], "default": "body" }
      },
      "required": ["component", "text"]
    }
  ],
  "unevaluatedProperties": false
}
```

Key rules:

- **`component: { "const": "Text" }`** — the marker that says "this object IS
  a Text". The `discriminator.propertyName: "component"` in `anyComponent`
  tells validators/renderers to use that field to pick the type.
- **`required`** — which properties the model must always provide.
- `common_types.json#/$defs/...` refs come from the **A2UI spec's own bundled
  common types** (`DynamicString`, `ComponentId`, `ChildList`, `Action`,
  `Checkable`, …) — you do not need to ship that file; the SDK resolves it.
- The SDK's `remove_strict_validation` schema modifier strips
  `additionalProperties:false` / `unevaluatedProperties:false` before the
  schema goes into the prompt, so the model can add extra fields without being
  rejected — but component names and required fields are still enforced.
- **`$defs.anyComponent.oneOf`** must list every component (`$ref` to
  `#/components/<Name>`). Keep it in sync when you add/remove components.

## Where the catalog is used (three places)

1. **In the agent prompt** — `app/agent.py::build_inference_format()` builds a
   `DirectJsonFormat` (from `a2ui-agent-sdk`) with this catalog as its only
   catalog, plus `app/examples/`. When A2UI is active, the executor stores the
   resolved catalog in session state and the toolset renders
   `catalog.render_as_llm_instructions()` (schema + rules) into the LLM
   request.
2. **In validation** — the same catalog powers `A2uiValidator` (used by
   `DirectJsonParser` and by `send_a2ui_json_to_client`). The model's output
   is checked against it before it is accepted.
3. **Served to clients** — `GET /catalog.json` returns the file so a client
   can register renderers under the `catalogId`.

## Why the agent can't just invent components

Three independent layers:

1. **Prompt**: the model only *sees* the catalog's components + examples, and
   the instructions say "never invent components".
2. **Tool validation**: the model's payload goes through
   `send_a2ui_json_to_client`, which validates against the catalog and errors
   on unknown components / missing required fields. The model sees the error
   and retries.
3. **Client check**: even if something slipped through, the client looks up
   the renderer by component name; an unknown name has no renderer and is
   skipped/logged, never rendered as something else.

## Adding a custom component (the official recipe)

To add, say, a `Rating` component (1–5 stars):

1. **Add the schema to `app/catalog.json`** under `components`:

```json
"Rating": {
  "type": "object",
  "allOf": [
    { "$ref": "common_types.json#/$defs/ComponentCommon" },
    { "$ref": "#/$defs/CatalogComponentCommon" },
    {
      "type": "object",
      "properties": {
        "component": { "const": "Rating" },
        "value": { "type": "number", "minimum": 0, "maximum": 5,
                   "description": "Star rating 0-5." }
      },
      "required": ["component", "value"]
    }
  ],
  "unevaluatedProperties": false
}
```

2. **Add it to `$defs.anyComponent.oneOf`**:

```json
{ "$ref": "#/components/Rating" }
```

3. **Add an example** (optional but recommended) under `app/examples/`, e.g. a
   message list that includes a `Rating` — it is validated at startup, so it
   doubles as a test that your schema is right.

4. **Add a renderer in the a2ui-client repo's `client.js`**:

```js
Rating: (props) => {
  const el = document.createElement("span");
  el.textContent = "★".repeat(Math.round(props.value ?? 0)) + "☆".repeat(5 - Math.round(props.value ?? 0));
  el.style.color = "#fbbc04";
  return el;
},
```

5. Redeploy this agent (`./build.personal.sh && ./deploy.personal.sh`) and
   the client, then try it.

## Examples (`app/examples/`)

Each file is a complete, valid A2UI message list (usually
`createSurface` + `updateComponents`). They are:

- loaded + validated at startup (`validate_examples=True`),
- injected into the LLM request as few-shot templates when A2UI is active.

They teach the model the expected *shape*: start with `createSurface`
(carrying the real `catalogId`), then `updateComponents` with root first and
parents before children, ids referenced by string, `Text` used as button
labels, and so on.

## The `catalogId` agreement (recap)

1. The agent's card advertises
   `supportedCatalogIds: ["https://<APP_URL>/catalog.json"]`.
2. The client fetches that URL, registers renderers, and sends
   `a2uiClientCapabilities.supportedCatalogIds: [that same URL]`.
3. The executor intersects both → selects our catalog.
4. The agent's `createSurface` message carries that same `catalogId`.
5. The client checks the `catalogId` it already registered → renders.

If you deploy to a different URL, update `APP_URL` (env) and the
`catalogId`/`$id` in `catalog.json` to match — they must be the same public
URL. (The deploy scripts print the service URL; keep these in sync.)

Next: [05-glossary.md](05-glossary.md).
