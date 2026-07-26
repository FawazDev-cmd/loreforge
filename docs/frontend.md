# Frontend Foundation

LoreForge has one React frontend with two product surfaces:

- User Workspace for document and AskMe workflows.
- Admin and Engineering Panel for health, readiness, metrics, and evaluation views.

The frontend is a presentation layer. Backend authorization remains authoritative,
and route visibility must never be treated as access control.

## Stack

- React
- TypeScript
- Vite
- React Router
- TanStack Query
- React Hook Form
- Zod
- Vitest
- React Testing Library
- Lightweight CSS tokens in `src/styles/global.css`

## Structure

```text
frontend/
  src/
    api/          typed API client foundation and transport contracts
    app/          config, providers, and router setup
    components/   shared UI, navigation, loading, error, empty, and status states
    layouts/      public, workspace, and admin shells
    pages/        route-level presentation components
    schemas/      form validation schemas
    styles/       global tokens and responsive app layout
    test/         test setup
```

## Routes

```text
/                             public product entry
/login                        validated sign-in form shell
/workspace                    workspace overview
/workspace/documents          document list and ingestion status workflow
/workspace/documents/upload   PDF upload workflow
/workspace/chat               AskMe question and citation workflow
/admin                        engineering operations overview
/admin/system                 health and readiness view
/admin/metrics                operational metrics view
/admin/evaluation             offline evaluation posture
```

Workspace flow:

```text
Upload Documents -> wait until READY -> ask AskMe -> inspect citations
```

## Configuration

Copy the frontend template only for local overrides:

```powershell
Copy-Item frontend/.env.example frontend/.env
```

Supported variable:

```text
VITE_API_BASE_URL=http://127.0.0.1:8000
```

The value is validated as a URL at app startup.

## Development

Install frontend dependencies:

```powershell
cd frontend
npm install
```

Run the dev server:

```powershell
npm run dev
```

Run checks:

```powershell
npm run typecheck
npm test
npm run lint
npm run build
```

## API Boundary

`src/api/client.ts` provides:

- configured base URL handling
- JSON request and response handling
- bearer-token header injection
- request timeout support
- safe `ApiClientError` objects with status and request ID

It does not create sample data, call live providers, or weaken backend
authorization.

## Authentication

The backend authentication contract is bearer API-key based:

```text
Authorization: Bearer <api-key>
```

When authentication is enabled, missing or invalid credentials return `401` with
`{"detail":"authentication required"}` and `WWW-Authenticate: Bearer`.

The backend does not currently expose a traditional login endpoint, logout
endpoint, authenticated-user endpoint, or administrator role claim. The frontend
therefore verifies entered API keys with a lightweight authenticated
`GET /admin/documents` probe and stores the accepted credential only in
`sessionStorage`.

Frontend route protection:

- `/workspace` and `/workspace/*` redirect unauthenticated users to `/login`.
- `/admin` and `/admin/*` also require authentication.
- Admin routes are not role-gated because the backend exposes no RBAC/admin
  claim yet.
- A confirmed `401` from the API client clears the frontend session and returns
  the user to the login flow.
- Logout clears the frontend session and query cache only; there is no backend
  logout call in the current contract.

The frontend never renders the full API key after entry and never logs
authorization headers.

## Documents Workflow

The workspace documents route uses the authenticated catalog endpoint:

```text
GET /admin/documents
```

It renders filename, upload timestamp, page count, chunk count, and the exact
backend lifecycle status values:

```text
UPLOADED
INGESTING
READY
FAILED
DELETED
```

The upload route uses the existing upload boundary:

```text
POST /documents/upload
```

Supported upload constraints:

- one file per request
- PDF only
- `application/pdf`
- 10 MB maximum

Successful upload returns `status: "accepted"`. The frontend shows an
accepted-for-ingestion message, invalidates the document list query, and offers a
direct link back to the document list. Acceptance is not completion: the browser
never claims the document is READY until the backend document list reports READY.

The document list polls automatically about every 4.5 seconds while at least one
document is in an active state:

```text
UPLOADED
INGESTING
```

Polling stops when every returned document is terminal:

```text
READY
FAILED
DELETED
```

Manual refresh remains available.

## Query / AskMe Workflow

The workspace chat route integrates the existing authenticated AskMe endpoint:

```text
POST /ask
```

Request body:

```json
{"question":"What does the document say about refunds?"}
```

Successful responses include:

- `request_id`
- original `question`
- grounded `answer`
- ordered `citations`

Citation records expose the backend transport contract exactly:

- `citation_id`
- `document_id`
- `filename`
- `page_number`
- `chunk_id`

The frontend does not present a selected-document control because the current
backend `/ask` contract accepts only the question text. AskMe is described
truthfully as collection-wide retrieval across READY indexed documents owned by
the authenticated user. Documents still marked UPLOADED or INGESTING are not
presented as available for retrieval.

AskMe states:

- No uploaded documents: explain that a PDF must be uploaded first.
- No READY documents: explain that indexing is still running or no document is
  ready for retrieval.
- READY documents exist: enable the question form and show READY document count
  and concise filenames.

AskMe error handling:

- `401` clears the frontend session and returns the user to authentication.
- `422` displays validation guidance.
- `502` displays an insufficient-evidence state.
- `503` displays the degraded AskMe availability state.
- Other network or server failures are shown as safe generic errors.

The citation panel is expandable. The current backend response does not include
evidence excerpts, relevance scores, timestamps, or source-viewer URLs, so the
expanded panel shows citation metadata and clearly states that excerpt text is
not available yet. The frontend does not simulate streaming, fabricate evidence,
or create sample answers.


## Engineering Operations Panel

The `/admin` frontend surface is presented as Engineering Operations, not a
business administration console. It is intended to demonstrate production
readiness and observability without exposing unsupported controls.

Supported backend integrations:

```text
GET /health
GET /ready
GET /metrics
```

System view:

- API health from `/health`
- readiness from `/ready`
- safe placeholders for application version, configured provider, granular
  database readiness, and retrieval readiness when those fields are not exposed
  by the backend

Metrics view:

- authenticated `/metrics` JSON snapshot
- aggregate counter series
- aggregate duration series
- query trace count

Evaluation view:

- honest placeholder because no HTTP evaluation summary endpoint is currently
  exposed
- notes that deterministic evaluation and regression gates run through backend
  repository tooling

Unsupported operations are intentionally absent:

- users
- billing
- roles
- organizations
- permissions
- provider configuration
- destructive controls

The frontend never displays API keys, database URLs, Gemini credentials,
environment variables, internal filesystem paths, or other secrets.

## Current Limitations

- Evidence excerpts, relevance scores, timestamps, and document-scoped AskMe filtering are not exposed by the backend response yet.
- No frontend deployment artifact is connected to backend Docker packaging yet.

Frontend Day 7 completed the recruiter-focused polish pass and frontend freeze. The interface now emphasizes the five-minute demo path, consistent Workspace/Engineering language, honest backend limitations, and responsive accessibility polish.\n\nThe next milestone is Docker Verification and Production Validation.