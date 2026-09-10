# Mid-Level Python Backend Interview Guide & Scoring Rubric

## Evaluation Scale
* **5 (Excellent):** Deep understanding of underlying mechanics, clear communication, considers edge cases.
* **4 (Strong):** Correct implementation and concepts, minimal prompting needed.
* **3 (Adequate):** Understands the concept but struggles with implementation details or edge cases.
* **2 (Weak):** Fundamentally flawed understanding or requires heavy guidance.
* **1 (Fail):** Unable to answer or provides completely incorrect information.

---

## Q1: Python Architecture & Resource Management (Rate Limiter / Connection Manager)

**Question:** "How would you implement a rate-limiter or a database connection manager in Python to ensure resources are handled safely even if an error occurs?"

**Expected Answer:** The candidate should discuss using **Context Managers** (`__enter__` and `__exit__` methods) to ensure setup and teardown happen reliably. Alternatively, they could suggest using **Decorators** (with `functools.wraps`) to wrap functions with rate-limiting logic. 

**Scoring:**
* **Score 4-5:** Immediately suggests a Context Manager or Decorator. Explains `contextlib.contextmanager` or how `functools.wraps` preserves function metadata.
* **Score 3:** Mentions decorators/context managers but struggles to explain implementation from scratch. Over-relies on `try/except/finally`.
* **Score 1-2:** Suggests copying `try/except/finally` blocks everywhere. Doesn't understand how decorators intercept calls.

---

## Q2: Concurrency and The GIL (Slow Endpoint Profiling)

**Question:** "A backend endpoint you manage is running slowly. Profiling shows two distinct bottlenecks: one is making external API calls (I/O-bound), and the other is processing large JSON payloads (CPU-bound). How do you scale or optimize each in Python?"

**Expected Answer:** The candidate must distinguish between I/O and CPU bound tasks in the context of Python's **Global Interpreter Lock (GIL)**. For the I/O-bound task, `asyncio` or `threading` is appropriate. For the CPU-bound task, `multiprocessing` (which spawns separate processes, bypassing the GIL) or offloading to a worker/lower-level language is required.

**Scoring:**
* **Score 4-5:** Clearly defines the GIL. Correctly assigns `asyncio`/`threading` to I/O and `multiprocessing` to CPU-bound tasks.
* **Score 3:** Knows which library maps to which task type but struggles to explain *why* or vaguely understands the GIL.
* **Score 1-2:** Recommends `threading` for the CPU-bound JSON parsing. Unaware of the GIL.

---

## Q3: Database Interactions & ORM Inefficiencies (N+1 Problem)

**Question:** "What is the 'N+1 query problem', and how do you identify and resolve it in a Python backend?"

**Expected Answer:** N+1 occurs when code fetches a list of parent objects (1 query) and then iterates through them, executing an additional query for each child's related data (N queries). The solution is **eager loading**. For example, in SQLAlchemy (often used alongside Flask), this means using `joinedload` or `subqueryload`. In Django, it means `select_related` or `prefetch_related`.

**Scoring:**
* **Score 4-5:** Accurately describes N+1. Suggests eager loading using specific ORM methods to perform a SQL `JOIN` or a single `IN` clause.
* **Score 3:** Understands the looping inefficiency but forgets the specific ORM methods. Might suggest raw SQL joins over proper ORM usage.
* **Score 1-2:** Does not recognize the N+1 problem. Suggests increasing database connection pools or filtering all data in Python memory.

---

## Q4: API Design & System Behavior (Long-Running Report)

**Question:** "You need to expose an API endpoint that generates a complex report. The generation takes roughly 20 seconds. How do you design this API to prevent client timeouts and blocked threads?"

**Expected Answer:** Decouple the request from the processing. The API should immediately return an HTTP `202 Accepted` status with a `job_id`. The actual report generation is sent to a message broker and background task worker (like Celery + Redis/RabbitMQ). The client can then poll a status endpoint or wait for a webhook/WebSocket notification.

**Scoring:**
* **Score 4-5:** Proposes decoupling via HTTP 202, a task queue, and polling/webhooks for status updates.
* **Score 3:** Suggests backgrounding the task (e.g., native threads) but misses reliability concerns (e.g., server restarts).
* **Score 1-2:** Suggests increasing HTTP timeout limits and forcing synchronous waiting.

# Mid-Level Python Backend Interview Guide & Scoring Rubric
**Focus Areas:** Dependency Injection, Design Patterns, Framework Architecture (FastAPI, Django, Flask)  
**Target Duration:** 30 minutes (approx. 5–7 minutes per question)

---

## Evaluation Scale
* **5 (Excellent):** Deep architectural understanding, discusses trade-offs, clear communication, references testability/maintainability.
* **4 (Strong):** Correct conceptual explanation, provides clear practical examples, minimal prompting required.
* **3 (Adequate):** Familiar with concepts at a high level, but struggles with real-world implementation details or nuances.
* **2 (Weak):** Surface-level knowledge, confuses key architectural paradigms, requires significant guidance.
* **1 (Fail):** Inaccurate understanding or unable to answer.

---

## Q1: Dependency Injection (DI) & Testability
**Question:**  
"What is Dependency Injection (DI), how have you implemented or used it in Python (e.g., FastAPI's `Depends` or standard class-based DI), and how does it improve testing and decoupling?"

**Expected Answer:**  
* **Concept:** Providing required components (database sessions, external clients, configurations) from the outside rather than instantiating them inside the function or class.
* **Framework Implementation:** In FastAPI, `Depends` resolves dependencies per request, manages lifecycles (e.g., yielding a database session and closing it automatically), and enables easy overrides in tests (`app.dependency_overrides`).
* **General Python:** Constructor injection (`__init__`) allowing mock or stub objects to be injected during unit tests without modifying business logic.

**Scoring:**
* **Score 4–5:** Clearly explains inversion of control, explains FastAPI `Depends` (including yield dependencies/cleanup) or constructor injection, and highlights `app.dependency_overrides` or mocking for test isolation.
* **Score 3:** Understands DI as passing objects into functions/classes and mentions testability, but lacks clarity on dependency lifecycles or framework-level injection mechanisms.
* **Score 1–2:** Confuses DI with simple function arguments or inheritance; fails to explain why DI benefits testing or decoupling.

---

## Q2: Design Patterns in Backend Services
**Question:**  
"Can you walk me through a design pattern (e.g., Repository, Strategy, Factory, or Decorator) you have used in a Python backend application and explain what specific problem it solved?"

**Expected Answer:**  
The candidate should detail a concrete design pattern in backend architecture:
* **Repository Pattern:** Decouples business logic from data access/ORM layers, allowing storage layer refactoring or in-memory mocking without touching core logic.
* **Strategy Pattern:** Encapsulates interchangeable algorithms/behaviors (e.g., handling multiple payment gateways or export formats) behind a common interface.
* **Factory Pattern:** Centralizes dynamic object creation logic based on request parameters or configuration.
* **Decorator Pattern:** Cross-cutting concerns (authentication, caching, metrics tracking) without modifying core business functions.

**Scoring:**
* **Score 4–5:** Identifies a relevant pattern, explains the structural mechanics in Python, articulates the problem solved (maintainability, scalability, SRP), and mentions potential trade-offs (e.g., premature over-engineering).
* **Score 3:** Explains a pattern correctly in theory, but struggles to describe a practical backend use case or implementation in Python.
* **Score 1–2:** Names a pattern without understanding its purpose or describes standard procedural programming without applying the pattern correctly.

---

## Q3: Framework Comparison & Execution Models (FastAPI vs. Django vs. Flask)
**Question:**  
"How do Django, Flask, and FastAPI differ in their architecture, execution models (WSGI vs. ASGI), and ecosystem philosophy? In what scenarios would you choose one over the others?"

**Expected Answer:**  
* **Django:** "Batteries-included" monolithic web framework with built-in ORM, admin panel, auth, and migrations. Traditionally WSGI (synchronous request/response), with modern ASGI support. Best for rapid MVP development with relational databases and standard web interfaces.
* **Flask:** Minimalist WSGI microframework. Explicit configuration, unopinionated, relies on third-party extensions (SQLAlchemy, Celery). Best for lightweight services or when custom architectural flexibility is needed.
* **FastAPI:** Modern ASGI framework designed natively for async I/O. Built on Starlette and Pydantic for data validation, type hints, automatic OpenAPI/Swagger documentation, and native dependency injection. Best for high-concurrency microservices, APIs, and real-time endpoints.

**Scoring:**
* **Score 4–5:** Accurately compares all three across WSGI vs. ASGI, ecosystem breadth (batteries-included vs. microframework), data validation (Pydantic vs. Django Forms/Serializers), and provides justified decision criteria.
* **Score 3:** Knows the basic differences (Django has everything, Flask is minimal, FastAPI is fast/async) but cannot explain WSGI vs. ASGI or the underlying runtime differences.
* **Score 1–2:** Thinks FastAPI and Flask are interchangeable without understanding async/ASGI, or misidentifies core framework roles.

---

## Q4: Request Lifecycle, Middleware, & Custom Hooks
**Question:**  
"How does the request-response lifecycle work across backend frameworks, and what types of cross-cutting concerns should be handled in Middleware versus route-level handlers or dependencies?"

**Expected Answer:**  
* **Request Lifecycle:** Incoming request reaches the server (e.g., Gunicorn/Uvicorn) -> Middleware stack -> Routing -> Route Handlers/Dependencies -> Serialization -> Response Middleware -> Client.
* **Middleware Responsibilities:** Global, request-agnostic concerns such as CORS headers, global request logging, trace IDs, rate-limiting, and top-level error interception.
* **Handler/Dependency Responsibilities:** Route-specific authentication/authorization, request body schema validation, and database transaction lifecycles.

**Scoring:**
* **Score 4–5:** Clearly maps the flow from gateway/server through middleware to handlers. Distinguishes global cross-cutting concerns (Middleware) from route-specific validations/dependencies.
* **Score 3:** Understands middleware intercepts requests/responses, but blurs the line between middleware responsibilities and route handler business logic.
* **Score 1–2:** Unable to explain how middleware functions or suggests placing database transactions and business logic entirely inside global middleware.