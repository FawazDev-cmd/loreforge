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
/workspace/documents          document list shell
/workspace/documents/upload   upload shell
/workspace/chat               AskMe shell
/admin                        admin overview
/admin/system                 system status shell
/admin/evaluation             evaluation shell
```

These routes are intentionally lightweight. They reserve the product information
architecture without inventing data, fake answers, fake documents, or unsupported
admin workflows.

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
- future bearer-token header injection
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

Successful upload returns `status: "accepted"`. The frontend shows acceptance
feedback and invalidates the document list query, but it does not fake catalog
registration or ingestion completion. Current ingestion state remains whatever
the backend returns from the document list endpoint.

## Current Limitations

- AskMe, system, metrics, and evaluation views are shells.
- No frontend deployment artifact is connected to backend Docker packaging yet.

The next milestone is Frontend Day 4: Question, Answer, and Citation Experience.
