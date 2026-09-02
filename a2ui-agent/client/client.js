// Minimal A2UI demo client: discovers the agent card, registers the custom
// catalog's components as renderers, sends A2A JSON-RPC messages with the
// A2UI extension, and renders incoming A2UI DataParts into the #surface div.

const APP_URL = window.location.origin; // served from the same FastAPI app
const CARD_URL = `${APP_URL}/.well-known/agent-card.json`;
const CATALOG_URL = `${APP_URL}/catalog.json`;
const RPC_URL = `${APP_URL}/a2a/a2ui_agent`; // A2A JSON-RPC endpoint (single POST)

const A2UI_EXT = "https://a2ui.org/a2a-extension/a2ui/v0.9";

const $ = (id) => document.getElementById(id);
const statusEl = $("status");

// ---- tiny state ----
let catalogId = null;
let surfaceEl = null; // current surface DOM root (per surfaceId)
const componentEls = new Map(); // component id -> element

// ---- component renderers: catalog component name -> (props, nodeId) => element ----
const renderers = {
  Text: (props) => {
    const el = document.createElement("div");
    el.className = `a2ui-text ${props.variant || "body"}`;
    el.textContent = props.text ?? "";
    return el;
  },
  Button: (props) => {
    const el = document.createElement("button");
    el.className = `a2ui-btn ${props.variant || "default"}`;
    el.textContent = props.child ? componentText(props.child) : props.label ?? "";
    if (props.action?.event?.name) {
      el.addEventListener("click", () => logEvent(`button clicked: ${props.action.event.name}`));
    }
    return el;
  },
  Row: (props) => {
    const el = document.createElement("div");
    el.className = "a2ui-row";
    if (props.justify) el.style.justifyContent = justifyToCss(props.justify);
    if (props.align) el.style.alignItems = alignToCss(props.align);
    (props.children || []).forEach((id) => {
      const child = componentEls.get(id);
      if (child) el.appendChild(child);
    });
    return el;
  },
  Column: (props) => {
    const el = document.createElement("div");
    el.className = "a2ui-col";
    if (props.justify) el.style.justifyContent = justifyToCss(props.justify);
    if (props.align) el.style.alignItems = alignToCss(props.align);
    (props.children || []).forEach((id) => {
      const child = componentEls.get(id);
      if (child) el.appendChild(child);
    });
    return el;
  },
  Card: (props) => {
    const el = document.createElement("div");
    el.className = "a2ui-card";
    if (props.title) {
      const t = document.createElement("div");
      t.className = "a2ui-title";
      t.textContent = props.title;
      el.appendChild(t);
    }
    const child = componentEls.get(props.child);
    if (child) el.appendChild(child);
    return el;
  },
};

function componentText(id) {
  const el = componentEls.get(id);
  return el ? el.textContent : "";
}
function justifyToCss(v) {
  return { spaceBetween: "space-between", spaceAround: "space-around", spaceEvenly: "space-evenly" }[v] || v;
}
function alignToCss(v) {
  return v;
}

// ---- catalog registration ----
async function loadCatalog() {
  const cat = await (await fetch(CATALOG_URL)).json();
  catalogId = cat.catalogId;
  statusEl.textContent = `catalog: ${catalogId}`;
  log("event", `Registered catalog ${catalogId} with components: ${Object.keys(cat.components).join(", ")}`);
}

// ---- A2A JSON-RPC (message/send; single POST, JSON result) ----
async function sendMessage(text) {
  log("user", text);
  const message = {
    messageId: `m-${crypto.randomUUID()}`,
    role: "user",
    parts: [{ text }],
    extensions: [A2UI_EXT],
    metadata: catalogId ? { a2uiClientCapabilities: { supportedCatalogIds: [catalogId] } } : undefined,
  };

  try {
    const resp = await fetch(`${RPC_URL}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        id: crypto.randomUUID(),
        jsonrpc: "2.0",
        method: "message/send",
        params: { message },
      }),
    });
    if (!resp.ok) {
      const err = await resp.text();
      throw new Error(`HTTP ${resp.status}: ${err.slice(0, 400)}`);
    }
    const rpc = await resp.json();
    if (rpc.error) throw new Error(JSON.stringify(rpc.error));
    handleTaskResult(rpc.result);
  } catch (e) {
    log("event", `error: ${e.message}`);
    statusEl.textContent = "error";
  }
}

function handleTaskResult(result) {
  // result.artifacts[].parts[] and result.history[] carry Text + Data parts.
  const parts = [];
  (result.artifacts || []).forEach((a) => (a.parts || []).forEach((p) => parts.push(p)));
  (result.history || []).forEach((m) => {
    if (m.role === "agent") (m.parts || []).forEach((p) => parts.push(p));
  });
  parts.forEach((p) => {
    if (p.kind === "text") log("agent", p.text);
    else if (p.kind === "data" && p.data) renderA2UI(p.data);
  });
  if (result.status?.state) statusEl.textContent = result.status.state;
}

// ---- A2UI rendering ----
function renderA2UI(msg) {
  if (msg.createSurface) {
    const { surfaceId, catalogId: cid } = msg.createSurface;
    if (cid && cid !== catalogId) log("event", `warning: surface catalog ${cid} != registered ${catalogId}`);
    surfaceEl = document.createElement("div");
    surfaceEl.dataset.surfaceId = surfaceId;
    $("surface").replaceChildren(surfaceEl);
    log("event", `createSurface ${surfaceId}`);
  } else if (msg.updateComponents) {
    const { components } = msg.updateComponents;
    if (!surfaceEl) {
      surfaceEl = document.createElement("div");
      $("surface").replaceChildren(surfaceEl);
    }
    // register components by id (parents before children per protocol)
    components.forEach((c) => {
      const renderer = renderers[c.component];
      if (!renderer) {
        log("event", `no renderer for component '${c.component}'`);
        return;
      }
      const el = renderer(c);
      el.dataset.cid = c.id;
      componentEls.set(c.id, el);
    });
    // attach root: find the component with no parent reference (children/child refs)
    const refd = new Set();
    components.forEach((c) => {
      const list = c.children || (c.child ? [c.child] : []);
      list.forEach((id) => refd.add(id));
    });
    const roots = components.filter((c) => !refd.has(c.id));
    const root = roots[0];
    if (root) {
      const el = componentEls.get(root.id);
      surfaceEl.replaceChildren(el);
    }
    log("event", `updateComponents (${components.length} components)`);
  }
}

function log(cls, text) {
  const div = document.createElement("div");
  div.className = `msg ${cls}`;
  div.textContent = text;
  $("chatLog").appendChild(div);
  $("chatLog").scrollTop = $("chatLog").scrollHeight;
}
function logEvent(text) {
  log("event", `⏎ ${text}`);
}

async function init() {
  try {
    const card = await (await fetch(CARD_URL)).json();
    log("event", `Agent card: ${card.name}`);
    const ext = (card.capabilities?.extensions || []).find((e) => e.uri === A2UI_EXT);
    if (!ext) log("event", "WARNING: agent does not advertise the A2UI extension");
    else statusEl.textContent = `A2UI ext v0.9 supported`;
    await loadCatalog();
  } catch (e) {
    log("event", `discovery failed: ${e.message}`);
    statusEl.textContent = "discovery failed";
  }
}

$("send").addEventListener("click", () => {
  const v = $("prompt").value.trim();
  if (v) sendMessage(v);
});
$("prompt").addEventListener("keydown", (e) => { if (e.key === "Enter") $("send").click(); });
$("demoA2UI").addEventListener("click", () => sendMessage("show me an A2UI demo with a button and some text"));
$("demoText").addEventListener("click", () => sendMessage("what is the capital of France?"));

init();
