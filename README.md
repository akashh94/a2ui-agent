# a2ui-agent

A single-repo, two-service project: an ADK `LlmAgent` (Google Search + an A2UI
catalog tool) deployed on **Vertex AI Agent Engine**, and a **Cloud Run**
catalog + chat facade that serves the A2UI catalog and streams `/chat`
responses to the deployed agent.

```
Browser / client
   │  HTTPS (public)
   ▼
a2ui-server (Cloud Run) ── GET /etcatalog (static catalog.json)
   │                       ── POST /chat (SSE proxy)
   │                             │
   │                             │ Vertex AI API (SA/ADC, gRPC)
   ▼                             ▼
                         a2ui-agent (Agent Engine)
                               │
                               │ ID-token auth (RestApiTool, audience=catalog URL)
                               ▼
                         a2ui-server /etcatalog (private, IAM-only)
```

- **a2ui-server/** — Cloud Run. Serves `GET /etcatalog` (the A2UI catalog as
  JSON, official v0.9 JSON Schema format, same shape as `@a2ui/lit`'s
  published basic catalog) and `POST /chat`, which streams the agent's reply
  as SSE. `/chat` is a thin proxy: it forwards the message to the deployed
  Agent Engine and relays streamed events back to the client.
- **a2ui-agent/** — Agent Engine. The ADK `LlmAgent` with two tools:
  `google_search` for general web questions, and `get_a2ui_catalog`, a REST
  tool that fetches the catalog from the a2ui-server over HTTP using a
  service-account **ID token** (audience = the catalog URL). The model decides
  *when* to call the catalog tool; it never authors component JSON itself.

The catalog is data the agent fetches from the a2ui-server — the model
never authors component JSON itself, and the agent has no local copy.

## How the two tools split the work

- **`google_search`** — general web questions ("what is the capital of
  France?").
- **`get_a2ui_catalog`** — calls `GET <a2ui-server>/etcatalog` via a
  `RestApiTool` (from an `OpenAPIToolset`), authenticated with the Agent
  Engine service account's ID token. Same catalog `/etcatalog` serves.

## Setup (local)

Each service is self-contained; install and run them separately.

```bash
# a2ui-server (FastAPI + vertexai client)
cd a2ui-server
pip install -r requirements.txt
cp .env.example .env   # (see below)

# a2ui-agent (ADK agent)
cd a2ui-agent
uv sync   # or: pip install -e .
```

Authentication is via **Application Default Credentials (ADC)** — no API keys:

```bash
gcloud auth application-default login
```

## Run (local)

### a2ui-server

```bash
cd a2ui-server
uvicorn server:app --reload
```

Each SSE frame is `data: <json>`; text deltas stream as they are generated
and the stream ends with `data: [DONE]`.

Catalog:

```bash
curl http://localhost:8000/etcatalog
```

Chat — the local `/chat` proxies to the Agent Engine identified by
`AGENT_ENGINE_PROJECT` / `AGENT_ENGINE_LOCATION` / `AGENT_ENGINE_ID` (set them
to your deployed agent):

```bash
curl -N -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "what is the capital of France?"}'
```

### a2ui-agent

```bash
cd a2ui-agent
python -c "from agent import agent; print(agent.name)"   # smoke test
```

## Deploy (two services)

Deploy **a2ui-server first**, then **a2ui-agent** (the agent needs the catalog
URL + the a2ui-server must be up to answer the catalog tool).

Each service has office/personal variants following the geap-agent convention
(`./build.sh` then `./deploy.sh`, or `./build.personal.sh` then
`./deploy.personal.sh`), with config from `a2ui.deploy.env` / `deploy.personal.env`.

### 1. a2ui-server → Cloud Run

1. Edit `a2ui-server/a2ui.deploy.env` (or `deploy.personal.env`): set
   `PROJECT_ID`, `REGION`, and after first deploy `PROJECT_ID_HASH` (the short
   hash in the printed service URL) and `CATALOG_URL`.
2. Build and deploy:

   ```bash
   cd a2ui-server
   ./build.sh && ./deploy.sh        # office
   # or ./build.personal.sh && ./deploy.personal.sh
   ```

3. Give the **a2ui-agent service account** `roles/run.invoker` on this
   Cloud Run service (so the agent's catalog tool can call `/etcatalog` with
   its ID token). agents-cli provisions the engine's service account; find
   its email with `gcloud iam service-accounts list`. Example:

   ```bash
   gcloud run services add-iam-policy-binding a2ui-server \
     --region us-central1 --member serviceAccount:SA_EMAIL \
     --role roles/run.invoker
   ```

### 2. a2ui-agent → Agent Engine

Deployment is driven by `agents-cli` (the same flow as geap-agent): the
manifest `agents-cli-manifest.yaml` defines the Agent Engine target, and
`deploy.sh`/`deploy.personal.sh` pass the runtime env vars via
`--update-env-vars`. No service account is passed — agents-cli provisions one
(Vertex AI User on the project).

1. Edit `a2ui-agent/a2ui.deploy.env` (or `deploy.personal.env`): set
   `PROJECT_ID`, `REGION`, and `CATALOG_URL` to the deployed a2ui-server URL.
2. Build and deploy:

   ```bash
   cd a2ui-agent
   ./build.sh && ./deploy.sh        # office
   # or ./build.personal.sh && ./deploy.personal.sh
   ```

   `build.sh` runs `agents-cli install` + `agents-cli lint`; `deploy.sh` runs
   `agents-cli deploy --deployment-target agent_runtime` (creates or updates
   the engine, and pushes the container to Artifact Registry).

3. Give the **a2ui-server service account** `roles/aiplatform.user` on the
   project so its `/chat` proxy can call the Agent Engine.

### 3. Point the facade at the agent

Set `AGENT_ENGINE_PROJECT` / `AGENT_ENGINE_LOCATION` / `AGENT_ENGINE_ID` (the
engine's project, region, and `reasoningEngines/<id>` from the deploy output)
in `a2ui-server`'s env file and redeploy the a2ui-server (or update the env
vars in the Cloud Run console). Then the public `/chat` endpoint streams from
your deployed agent.

## IAM / service accounts at a glance

| Direction | Identity | Grant |
|---|---|---|
| a2ui-server → Agent Engine (`/chat`) | Cloud Run SA | `roles/aiplatform.user` on the project |
| Agent Engine → a2ui-server `/etcatalog` (catalog tool) | Agent Engine SA (provisioned by agents-cli) | `roles/run.invoker` on the a2ui-server |

No API-key secrets anywhere — everything rides on ADC + service accounts.

## Project layout

```
a2ui-server/         Cloud Run: catalog.json + server.py (catalog + chat SSE proxy)
  server.py          FastAPI app: GET /etcatalog, POST /chat (SSE)
  catalog.json       A2UI catalog, official v0.9 JSON Schema format
  Dockerfile         Container image for Cloud Run (PORT-aware)
  build.sh / deploy.sh            Office: build + deploy to Cloud Run
  build.personal.sh / deploy.personal.sh  Personal variants
  a2ui.deploy.env / deploy.personal.env   Deployment config
a2ui-agent/          Agent Engine: the ADK agent + agents-cli deployment
  agent.py           ADK LlmAgent: google_search + get_a2ui_catalog (RestApiTool)
  agents-cli-manifest.yaml  Manifest for agents-cli (Agent Engine target)
  pyproject.toml     Package metadata (agents-cli installs the agent)
  build.sh / deploy.sh            Office: build + deploy to Agent Engine
  build.personal.sh / deploy.personal.sh  Personal variants
  a2ui.deploy.env / deploy.personal.env   Deployment config
```

## Deliberately out of scope

No frontend/renderer, no A2UI envelope builder, no validation layer, no DB or
auth on the a2ui-server (public demo). Session persistence is handled by
Agent Engine's managed session/memory services. A future client can consume
`/etcatalog` + `/chat` directly.
Q1: The Left-Prefix Rule & B-Tree Mechanics
Question: "You have a massive users table with a composite index on (last_name, first_name). You write the following query: SELECT * FROM users WHERE first_name = 'Alice';. 
The database is slow and execution plans show a Full Table Scan. Why didn't it use the index, and how do you fix it?"

First Principles Focus: B-Tree traversal and composite index structuring.

Expected Answer: A composite index is structured hierarchically. The B-Tree is sorted first by last_name, and then by first_name within those last names. 
Searching for just first_name is like looking for someone named "Alice" in a phone book without knowing their last name—you still have to read the whole book.

The Fix: Create a separate index on first_name, or if the query frequently filters by both, ensure the WHERE clause includes the leading column of the index (last_name).

========================================================================================================================================================================================

Question: "Look at these two transactions executing concurrently in your backend. Occasionally, both transactions fail. What fundamental database concept is causing the crash, and how do you resolve it architecturally?"

BEGIN;
UPDATE inventory SET stock = stock - 1 WHERE item_id = 100;
UPDATE users SET balance = balance - 50 WHERE user_id = 5;
COMMIT;

BEGIN;
UPDATE users SET balance = balance + 50 WHERE user_id = 5;
UPDATE inventory SET stock = stock + 1 WHERE item_id = 100;
COMMIT;

First Principles Focus: Lock acquisition, isolation levels, and Deadlocks.

Expected Answer: This is a classic Deadlock. Transaction A locks the inventory row and waits for the users row. 
Transaction B locks the users row and waits for the inventory row. They wait on each other infinitely until the database's deadlock detector kills one.

The Fix: Enforce a strict lock acquisition order across the entire application. For example, 
always update tables in alphabetical order (always lock inventory before users), ensuring threads queue sequentially rather than deadlocking.

========================================================================================================================================================================================
import json
import requests
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

# ==========================================
# 1. I/O-Bound Task: Network Calls
# ==========================================
def fetch_api_data(url):
    """Simulates a slow network call (I/O bound)."""
    response = requests.get(url)
    return response.text

def fetch_all_data_concurrently(urls):
    """
    SOLUTION: Use Threading (or asyncio).
    WHY: When a thread makes a network request, it sits idle waiting for the response. 
    Python releases the GIL during this idle I/O time, allowing other threads to run 
    and make their own requests simultaneously.
    """
    # Using threads is safe and efficient here
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(fetch_api_data, urls))
    return results


# ==========================================
# 2. CPU-Bound Task: Heavy JSON Parsing
# ==========================================
def process_massive_json(raw_json_string):
    """Simulates heavy CPU work (CPU bound)."""
    data = json.loads(raw_json_string)
    # Simulate heavy computation on the parsed data
    return sum(item['value'] ** 2 for item in data)

def process_all_payloads_parallel(payloads):
    """
    SOLUTION: Use Multiprocessing.
    WHY: Parsing JSON and doing math requires continuous CPU cycles. If we used threads, 
    the GIL would force them to execute one at a time, resulting in zero performance gain 
    (and potentially worse performance due to context switching). 
    Multiprocessing spawns entirely new OS processes, each with its own memory space 
    and its own GIL, allowing true parallel execution across multiple CPU cores.
    """
    # Threads would fail here. We must use processes.
    with ProcessPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(process_massive_json, payloads))
    return results



    """
    CANDIDATE PROMPT:
    A previous developer wrote this pipeline to speed up execution. 
    However, profiling shows that Task 2 is still extremely slow and maxing out 
    only a single CPU core, despite using multiple threads.
    
    1. Explain why Task 2 is not truly running in parallel.
    2. Rewrite `run_pipeline` to correctly optimize both Task 1 and Task 2.
    """
	
import json
import requests
from concurrent.futures import ThreadPoolExecutor

def fetch_api_data(url):
    response = requests.get(url)
    return response.text

def process_massive_json(raw_json_string):
    data = json.loads(raw_json_string)
    return sum(item['value'] ** 2 for item in data)

def run_pipeline(urls, payloads):
    
    with ThreadPoolExecutor(max_workers=8) as executor:
        
        # Task 1: Fetch data from external APIs
        print("Starting network calls...")
        api_results = list(executor.map(fetch_api_data, urls))
        
        # Task 2: Process JSON payloads
        processed_results = list(executor.map(process_massive_json, payloads))
        
    return api_results, processed_results

# Example execution:
# urls = ["http://example.com/api/1", "http://example.com/api/2", ...]
# payloads = ['{"value": 1}', '{"value": 2}', ...]
# run_pipeline(urls, payloads)

ls=[1,2.3.[4,5,[6,7]]]

class AWSSESEmailClient:
    def send(self, email_address, message):
        print(f"Connecting to AWS SES... Sending '{message}' to {email_address}")
        # Imagine actual SMTP network code here
        return True

class UserService:
    def __init__(self):
        self.email_client = AWSSESEmailClient()

    def register_user(self, username, email):
        # ... logic to save user to database ...
        print(f"User {username} saved to database.")
        
        # Sending the welcome email
        self.email_client.send(email, "Welcome to our platform!")
		
==========================================================================================================================================================
Question: 
Take a look at this Python function. It reads a JSON file, extracts a specific value, and returns a processed result. 
If an error occurs while this function is running, what exactly goes wrong at the system level, and how would you rewrite this to prevent it?

import json

def extract_and_process(file_path):
    file = open(file_path, 'r')
    
    # Load the JSON data
    data = json.load(file)
    
    # Process the target metric
    processed_data = data['target_metric'] * 100
    
    file.close()
    return processed_data
	
==========================================================================================================================================================

ls = [1,2,3,[4,5,[6,7]]]
output=[1,2,3,4,5,6,7]

==========================================================================================================================================================

exp = "1+2*(3+1)"
out = 9

My mother has problem with her spine L4 and L5. The doctor suggested first to with some sessions of therapy. If that did not worked out, then they need to operate. 
And there is no one who can take her to the therapy sessions weekly twice.
so I need go to my hometown to help her in that. I need WFH in the month of November and december.

I am writing to request approval to work remotely from my hometown for the months of November and December (November 1 – December 31).

My mother is dealing with a severe spinal condition affecting her L4–L5 vertebrae. 
Her specialist has initiated an intensive twice-weekly physiotherapy program to evaluate whether surgery can be avoided. 
Since no one else is available locally to take her to these hospital sessions, I need to be home to support her through this critical phase.

How I will manage work and availability:
Zero operational impact: The therapy sessions require about 1.5 to 2 hours twice a week. 
I will schedule these outside core team hours or adjust my start/end times so my total working hours remain fully covered.
Standard availability: I will maintain all regular business hours, team standups, sprint commitments, and instant responsiveness on Slack/Teams
Accountability: I am happy to set up a quick bi-weekly review with you to ensure all deliverables and velocity remain completely on track.
Working remotely allows me to stay fully engaged with our deliverables without needing to take sudden personal leave.

# NEW 2 - notepad++ file
Here is a quick FastAPI endpoint that calls an LLM. It technically works, but it's causing server timeouts. 
Walk me through what is wrong with the Python code

from fastapi import FastAPI
import requests

app = FastAPI()

@app.get("/generate")
async def generate_text(prompt: str):
    # Calling an external LLM API
    response = requests.post(
        "https://api.llmprovider.com/v1/completions", 
        json={"prompt": prompt}
    )
    return response.json()
	
"You've built a FastAPI application that handles 5,000 requests per minute. Each request needs to query a database and occasionally call an external LLM API. 
The application keeps crashing due to memory leaks and connection timeouts."

Walk me through how you would diagnose this. Where does an OOP pattern like Singleton make sense here, and where would Dependency Injection actually save us?"

­ЪДа What to Look For (Evaluation Guide)
Do not prompt the candidate with the answers; wait for them to break down the problem structurally and apply the concepts.


Database Connections: The candidate should immediately mention Connection Pooling for the database.


The Async Trap: They should demonstrate an understanding of FastAPI's async (async/await) behavior, specifically noting that blocking I/O (like making a synchronous LLM API call) will freeze the event loop.


The Dependency Injection Solution: They should explicitly explain how Dependency Injection in FastAPI (typically via Depends) allows for clean testing and 
connection teardown. A strong candidate will point out that injecting the database session ensures the connection is properly closed or returned to the pool 
automatically after the request completes, which is what prevents the memory leaks and timeouts in this scenario.

project id: adk-tut-499512

Personal
PROJECT ID: adk-tut-499512
ARTIFACT REGISTRY: akapal-geap-ui
My deployed agent query url: https://us-central1-aiplatform.googleapis.com/v1/projects/adk-tut-499512/locations/us-central1/reasoningEngines/5062056426524901376:query

Office
PROJECT ID: labs-gcp-msls-16495-1782829337
Top pick: Financial Planning / Wealth Advisor

https://adk.dev/sessions/memory/
https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/adk-quickstart
https://cloud.google.com/blog/topics/developers-practitioners/multi-agent-architecture-and-long-term-memory-with-adk-mcp-and-cloud-run
https://codelabs.developers.google.com/codelabs/christmas-card/instructions
https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank



   # NEW 1 - notepad++ file
In adk, there are 2 components which handle memory management and execution.
SessionService and Runner

LLM purane messages save kar ke nahi rakh sakta.to ek session ki state ko save karne k liye hum SessionService ka use karte hai
iski core responsibilities hoti hai
1. Context isolation: Kisi ek user ki saved state kisi dusre user ko na dikhe ya mile.
2. Event tracking: Events ko maintain karna. jab bhi ek user koi message bhejta hai to ek k bad ek events occur hote hai jaise ki tool called, user query received, llm resposne
3, state management: agar hume kuch data store karna hota hai structured format me, jaise ki user ka naam, ya fir koi important detail to use hum state dictionary me save kar sakte hai.

Production environment me hume SessionService ko persistant database k sath map karna chahiye kyuki bina uske ye data bas ram me persist karega jo application k restart hote hi chala jayega.

 :
Runner ki core responsibilities hoti hai:
1. Execution loop: Jab bhi ek user message bhejta hai to Runner ek while loop start karta hai. User k bheje hue message ko prompt aur SessionService me saved details k sath jodkar LLM ko bhejta hai.
2. Tool Orchestration: Agar LLM ko kisi tool ko call karne ki jarurat hoti hai to LLM pause ho jata hai, Runner current request ko intercept karta hai aur python function(tool) ko run karta hai,
						result capture karke vapas llm ko bhej deta hai
3. Event yielding: Jab b ek user ek message bhejta hai to bahut sare events occur hote hai. Jab sab complete ho jata hai tab hume final result milta hai.
					Runner jitne b events occur hote hai un sabko step by step return karta rehta hai. jaise ki 
					User asks: "What is the weather in London?
					System Event: Runner starts processing the prompt.

					LLM Event: The LLM evaluates the prompt and realizes it needs data. It outputs a ToolCall request (not text). The Runner yields an event indicating a tool 
					has been requested.

					Execution Event: The Runner pauses the LLM, finds your Python get_weather function, and executes it. It yields an event showing the tool is running.

					Result Event: The tool finishes and returns {"status": "success", "report": "15°C"}. The Runner yields an event containing this payload and sends it back to 
					the LLM.

					Final Generation Event: The LLM receives the tool's data, synthesizes it, and generates the final English sentence: "The weather in London is 15°C."

mistral: n7BbJflmC1CJxTdBTsOvyRG7hikCUDjV

Operating Instructions

Prioritize accuracy over speed or speculation.
Never assume, infer, or fabricate information. If information is missing or uncertain, verify it using reliable internet sources when available.
If the information cannot be verified or does not exist, reply: **"I don't have reliable information to answer that."**
Keep responses concise and focused. Avoid unnecessary explanations, repetition, or filler.
Stay strictly on the requested topic unless additional context is essential.
Assume every response will be reviewed by another AI or subject-matter expert. Make reasoning explicit when needed and avoid unsupported claims.
Do not automatically agree with my statements or conclusions. Treat them as hypotheses to evaluate.
For every significant claim or proposal I make:
  1. Identify assumptions that may be incorrect.
  2. Present reasonable counterarguments or skeptical viewpoints.
  3. Test the logic for gaps, inconsistencies, or unsupported inferences.
  4. Offer alternative interpretations or approaches.
  5. Correct me clearly when the evidence or reasoning does not support my conclusion.
Be constructive, objective, and intellectually rigorous. Challenge ideas, not people.
Call out confirmation bias, logical fallacies, or weak reasoning whenever they appear.
Prefer evidence over opinion and truth over agreement.
When uncertain, explicitly state the level of confidence and why.
Separate verified facts, logical inference, and speculation whenever applicable.

D:/adk_tut/runner_and_session
				|
				---src
					|   main.py
					|   __init__.py
					|   
					+---agents
					|   \---answer_agent
					|       |   agent.py
					|       |   
					|       \---__pycache__
					|               agent.cpython-312.pyc
					|               
					+---core
					|   |   config.py
					|   |   runner.py
					|   |   session_manager.py
					|   |   
					|   \---__pycache__
					|           runner.cpython-312.pyc
					|           session_manager.cpython-312.pyc
					|           
					+---tools
					\---__pycache__
							main.cpython-312.pyc
							__init__.cpython-312.pyc

   
  


# def merge(final_arr, si, mid, ei):

#     arr = final_arr.copy()
#     i = si #iterator for left
#     j = mid+1 #iterator for right
#     k = si

#     while(i <= mid and j <= ei):
#         if arr[i] < arr[j]:
#             final_arr[k] = arr[i]
#             i+=1
#         else:
#             final_arr[k] = arr[j]
#             j+=1
#         k+=1
#     while(i<=mid):
#         final_arr[k] = arr[i]
#         i+=1
#         k+=1
#     while(j<=ei):
#         final_arr[k] = arr[j]
#         j+=1
#         k+=1


# def merge_sort(arr, si, ei):
#     if si == ei:
#         return

#     mid = int(si + (ei - si)/2)
#     merge_sort(arr, si, mid)
#     merge_sort(arr, mid+1, ei)
#     merge(arr, si, mid, ei)

def merge(l, r, mid, arr):
    left = arr[l:mid+1]
    right = arr[mid+1:r+1]
    cur = l
    i=0
    j=0
    while(i < len(left) and j < len(right)):
        if left[i] < right[j]:
            arr[cur] = left[i]
            i+=1
        else:
            arr[cur] = right[j]
            j+=1
        cur+=1

    while(i < len(left)):
        arr[cur] = left[i]
        i+=1
        cur+=1
    while(j < len(right)):
        arr[cur] = right[j]
        j+=1
        cur+=1

def merge_sort(l, r, arr):
    if l>=r:
        return
    
    mid = l+int((r-l)/2)
    merge_sort(l, mid, arr)
    merge_sort(mid+1, r, arr)
    merge(l, r, mid, arr)

arr = [2,1,8,3,6,5]
print(merge_sort( 0, 5, arr))
print(arr)
