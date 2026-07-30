# RAGForge Frontend Map

RAGForge frontend is a Next.js App Router control-plane UI for authenticated RAG operations. It lets a user sign in, manage projects and organizations, upload and inspect documents, follow ingestion pipeline runs, ask streamed RAG questions, inspect citations and retrieval traces, and review query/observability history.

The frontend is intentionally tied to the existing FastAPI backend surface. It does not expose unsupported project description persistence, chunk editing, version rollback, knowledge-graph data, or fake dashboard metrics.

## Stack

| Area | Current implementation |
|---|---|
| Framework | Next.js App Router, React, TypeScript |
| Styling | Tailwind CSS v4 via `globals.css`, custom CSS variables, dark green/black RAGForge identity |
| Data fetching | TanStack Query with `staleTime: 15000`, retry `1`, no refetch on window focus |
| Forms | React Hook Form, Zod validation |
| Notifications | `sonner` toast system |
| Icons | `lucide-react` |
| Markdown | `react-markdown` with `remark-gfm` |
| Tests | Vitest, Testing Library, Playwright e2e |
| Auth model | HttpOnly session cookie handled by Next.js route handlers |

## Runtime Shape

```text
Browser UI
  -> /api/auth/login | /api/auth/register | /api/auth/logout
  -> HttpOnly ragforge_session cookie
  -> /api/backend/[...path] same-origin proxy
  -> FastAPI backend with Authorization: Bearer <token>
  -> Projects, documents, ingestion runs, query history, retrieval traces
```

The browser never reads or stores the backend JWT directly. The JWT is set by the login route as an HttpOnly cookie named `ragforge_session`.

## Main Directories

```text
frontend/
  Dockerfile
  package.json
  next.config.ts
  playwright.config.ts
  vitest.config.ts
  src/
    app/
      layout.tsx
      globals.css
      page.tsx
      api/
        auth/
          login/route.ts
          logout/route.ts
          register/route.ts
        backend/[...path]/route.ts
      (auth)/
        layout.tsx
        login/page.tsx
        register/page.tsx
      (dashboard)/
        layout.tsx
        home/page.tsx
        projects/page.tsx
        documents/page.tsx
        runs/page.tsx
        history/page.tsx
        observability/page.tsx
        organization/page.tsx
        settings/profile/page.tsx
        projects/[projectId]/
          page.tsx
          chat/page.tsx
          documents/page.tsx
          documents/[documentId]/page.tsx
          documents/[documentId]/versions/page.tsx
          runs/page.tsx
          runs/[runId]/page.tsx
          history/page.tsx
          history/[queryId]/page.tsx
          observability/page.tsx
          onboarding/page.tsx
          settings/page.tsx
    components/
      app-shell.tsx
      workspace/
      onboarding/
      ui/
    hooks/
    lib/
    test/
  e2e/
```

## Routes

| Route | Component | Purpose |
|---|---|---|
| `/` | `src/app/page.tsx` | Redirects to `/projects` |
| `/login` | `(auth)/login/page.tsx` | Validated login form, calls `/api/auth/login`, redirects to projects |
| `/register` | `(auth)/register/page.tsx` | Registration form, then auto-login and redirect |
| `/home` | `(dashboard)/home/page.tsx` | Cross-project metrics and recent project links |
| `/projects` | `(dashboard)/projects/page.tsx` | Project search, sort, grid/list, create, rename, delete |
| `/projects/[projectId]` | redirect | Redirects to project documents workspace |
| `/projects/[projectId]/chat` | redirect | Redirects to project documents workspace |
| `/projects/[projectId]/documents` | `WorkspaceEntry` | Main knowledge workspace: assistant, inspector, document panel |
| `/projects/[projectId]/documents/[documentId]` | `DocumentDetail` | Document overview, versions, runs, metadata, delete, version upload |
| `/projects/[projectId]/documents/[documentId]/versions` | `DocumentDetail` | Same document detail page opened on Versions tab |
| `/projects/[projectId]/onboarding` | `ProjectOnboarding` | Initial project source setup and ingestion progress |
| `/projects/[projectId]/runs` | `IngestionRunsPage` | Project-scoped ingestion run list |
| `/projects/[projectId]/runs/[runId]` | `IngestionRunDetail` | Live pipeline detail with SSE recovery |
| `/projects/[projectId]/history` | `QueryHistoryPage` | Project-scoped query history |
| `/projects/[projectId]/history/[queryId]` | `QueryDetail` | Persisted answer and retrieval trace |
| `/projects/[projectId]/observability` | `ObservabilityDashboard` | Project-scoped metrics from real records |
| `/projects/[projectId]/settings` | `ProjectSettingsPage` | Rename project, read storage identity, delete project |
| `/documents` | global page | Global document entry route exists in app tree |
| `/runs` | `IngestionRunsPage` | Cross-project ingestion run list |
| `/history` | `QueryHistoryPage` | Cross-project query history |
| `/observability` | `ObservabilityDashboard` | Cross-project observability |
| `/organization` | organization page | Organization create, rename, delete |
| `/settings/profile` | profile page | User identity, email, password, active organization |

## Authentication And Proxy

| File | Behavior |
|---|---|
| `src/lib/server-auth.ts` | Defines `AUTH_COOKIE = "ragforge_session"` and backend URL resolution from `BACKEND_URL` |
| `src/app/api/auth/login/route.ts` | Converts email/password JSON into FastAPI OAuth form login, stores `access_token` in HttpOnly cookie |
| `src/app/api/auth/register/route.ts` | Proxies registration JSON to backend |
| `src/app/api/auth/logout/route.ts` | Expires the session cookie |
| `src/app/api/backend/[...path]/route.ts` | Requires cookie, forwards selected request headers, injects `Authorization: Bearer`, streams backend body |
| `src/app/(dashboard)/layout.tsx` | Server-side guard; redirects unauthenticated users to `/login` |

Forwarded request headers are `accept`, `content-type`, and `last-event-id`. Forwarded response headers are `cache-control`, `content-disposition`, `content-type`, and `x-accel-buffering`.

## Data Layer

| File | Responsibility |
|---|---|
| `src/lib/api.ts` | `apiFetch` for `/api/backend/*`, `authFetch` for `/api/auth/*`, consistent JSON errors through `ApiError` |
| `src/lib/types.ts` | Shared control-plane types for users, organizations, projects, documents, ingestion runs, chunkers, query history, retrieval traces, SSE events |
| `src/lib/sse.ts` | Low-level SSE parser for streamed query and ingestion events |
| `src/lib/utils.ts` | Class merge, relative timestamps, latency formatting, avatar initials |
| `src/hooks/use-workspace-overview.ts` | Cross-project aggregation of projects, documents, runs, and query history |
| `src/hooks/use-ingestion-stream.ts` | Live ingestion SSE connection with `Last-Event-ID` replay and durable status recovery |

## Global App Shell

`src/components/app-shell.tsx` provides the authenticated application frame.

Implemented UX:

- Collapsible desktop sidebar with persisted collapsed state in `localStorage`.
- Mobile navigation drawer.
- Navigation entries for Home, Projects, Documents, Ingestion Runs, Query History, Observability, Organization, and Settings.
- Breadcrumbs derived from the current route and project name.
- Organization switcher using `/auth/me` PATCH.
- Global project search / command palette opened by button or `Ctrl/Cmd+K`.
- Notifications popover with empty state.
- User menu with profile link and sign out.
- Escape closes command palette, notifications, user menu, and mobile navigation.

Limitations:

- Command palette searches projects only.
- Notification center is presentational; pipeline failures are surfaced in ingestion views instead.
- Sidebar collapsed state is written but not read back on initial render.

## Design System

Reusable primitives:

| Component | Purpose |
|---|---|
| `Button` | Variants for primary, secondary, ghost, danger, icon sizes |
| `Input` | Shared input styling |
| `Dialog` | Modal wrapper with title, description, close behavior |
| `ConfirmDeleteDialog` | Destructive confirmation requiring the resource name |
| `EmptyState` | Empty collection state with optional action |
| `ErrorState` | Error panel with optional retry |
| `LoadingState` | Skeleton rows |
| `Badge` | Generic status/label badge |
| `StatusBadge` | Status-aware badge for ingestion, documents, query results, retrieval usage |
| `PageHeader` | Standard page heading/action area |
| `MetricCard` | Dashboard metric cards |

Visual notes:

- Dark background with green accent variables.
- Geist Sans and Geist Mono loaded globally.
- Icon-first controls through Lucide.
- Responsive layouts use grid/flex with mobile drawers for dense workspaces.
- The app uses many compact technical panels, matching an operational control-plane product.

## Project UX

Files:

- `src/app/(dashboard)/projects/page.tsx`
- `src/components/project-card.tsx`
- `src/components/project-form.tsx`
- `src/components/confirm-delete-dialog.tsx`

Implemented:

- List projects from `/projects/`.
- Search by name.
- Sort by recently updated or name.
- Toggle grid/list view.
- Per-project document count and active ingestion count loaded via document/run queries.
- Create project with name, organization, and default chunker browser preference.
- Rename project through `/projects/{project_id}` PATCH.
- Delete project through `/projects/{project_id}` DELETE with typed-name confirmation.
- Navigate new projects to onboarding.

Backend-aware limitations:

- Project descriptions are visible in the form as disabled because the current API does not support them.
- Advanced configuration is read-only and reflects backend defaults.
- Default chunking strategy is stored in browser local storage and applied during upload; it is not a project-level backend field.

## Main Knowledge Workspace

Files:

- `src/components/workspace/workspace-entry.tsx`
- `src/components/workspace/knowledge-workspace.tsx`
- `src/components/workspace/document-panel.tsx`
- `src/components/workspace/assistant-panel.tsx`
- `src/components/workspace/source-inspector.tsx`
- `src/components/workspace/workspace-data.ts`

The project documents route is the primary workspace. It combines assistant chat, source inspection, and knowledge source management.

Implemented layout:

- Main center surface with tabs for Assistant and Document.
- Right-side desktop knowledge panel, collapsible and horizontally resizable within bounds.
- Mobile document drawer.
- Mobile floating buttons for Documents and Document view.
- Citation opens the related document and switches to document inspection.

Implemented document panel:

- File upload, URL ingestion, and Google Drive ingestion.
- Chunker selector from `/chunkers`.
- Search documents.
- Filter by all/indexed/running/failed.
- Document rows with file-type icon, filename, source type, status, current version ID, updated time, selection checkbox, open document, details, upload new version link, version history link, ask-about-this scope action, retry failed ingestion, and delete.
- Active run progress summary for non-terminal runs.
- Failed run diagnostic snippet and retry action.
- Summary counts for documents, indexed documents, and active runs.

Implemented assistant:

- Empty state with prompt suggestions.
- Blocks query until at least one indexed document exists.
- Streams answers from `/rag/query/stream`.
- Supports provider selection between Gemini and Groq.
- Supports one selected document filter because the backend stream API accepts one `document_id`.
- Retrieval settings popover for parent context and citation loading.
- Stop generation via `AbortController`.
- Markdown answer rendering with GitHub-flavored Markdown.
- Execution trace steps: received, retrieved evidence, ranked sources, generated response, saved trace, verified citations.
- Citation chips after answer completion.
- Copy answer.
- Regenerate answer.
- Query history drawer with search and restore.

Implemented source inspector:

- Tabs: Content, Versions, Knowledge Graph, Retrieval Trace, Metadata.
- Content tab shows retrieved citation text only after a citation is selected.
- Versions tab loads `/documents/{document_id}/versions`.
- Retrieval Trace tab shows qdrant score, rerank score, strategy, rank, used-in-answer, chunk text.
- Metadata tab shows copyable document fields.
- Knowledge Graph tab explicitly reports unavailable backend support.

Limitations:

- Inspector does not fetch full extracted document content. It displays retrieved citation text when available.
- Knowledge graph is intentionally unavailable because no backend endpoint exists.
- Document enrichment fields such as size, pages, chunks, version, and owner are placeholders in `WorkspaceDocument` and not displayed as real metrics.
- Only one document ID is sent to the query stream even if UI selection logic could evolve later.

## Document Management

Files:

- `src/components/document-detail.tsx`
- `src/components/document-list.tsx`
- `src/components/documents-workspace.tsx`

Implemented document detail:

- Overview tab with source type, file type, current version, updated time, status.
- Versions tab with immutable version timeline, content hash, chunker, embedding model, error messages.
- Runs tab with compact ingestion pipelines for the document.
- Metadata tab with raw document fields.
- Upload new version. The UI requires the same filename so the backend creates a new document version.
- Ask about this links back to workspace with selected document.
- Delete document with typed-name confirmation.

Standalone documents page:

- Older upload/table experience still exists in `DocumentsWorkspace`.
- Supports file upload, chunker selector, active ingestion cards, search, and delete.
- Uses browser `window.confirm` for delete, unlike newer typed-name confirmation.

## Project Onboarding

File:

- `src/components/onboarding/project-onboarding.tsx`

Implemented:

- Step-based onboarding for a new project.
- Source options include file, URL, and Google Drive.
- Chunker selection.
- Creates file ingestion runs via `/ingest/file`.
- URL and Google Drive ingestion use synchronous backend endpoints.
- Uses `ProcessingRun` and `useIngestionStream` for live file-run progress.
- Retry failed ingestion run through `/ingest/runs/{run_id}/retry`.
- Continues to the workspace after source setup.

## Ingestion UX

Files:

- `src/components/ingestion-pipeline.tsx`
- `src/components/ingestion-card.tsx`
- `src/components/ingestion-run-detail.tsx`
- `src/components/ingestion-runs-page.tsx`
- `src/hooks/use-ingestion-stream.ts`

Pipeline stages shown:

1. Uploaded
2. Bronze landed
3. Parsing
4. Chunking
5. Silver completed
6. Embedding
7. Gold completed
8. Qdrant indexing
9. Indexed

Implemented:

- Project and cross-project ingestion run lists.
- Search by document filename or run ID.
- Filter by status.
- Live run detail page with connected/recovering indicator.
- SSE stream from `/ingest/runs/{run_id}/events`.
- `Last-Event-ID` persisted in local storage per run.
- Durable fallback fetch from `/ingest/runs/{run_id}` after stream failure.
- Retry failed runs from Bronze artifact.
- Failed-run panel with user explanation, technical details, open document link, and copy diagnostics.
- Created, started, and finished timestamps where backend provides them.

Limitations:

- Per-stage durations are not available from the current run type, so the UI shows stage completion and run timestamps instead.
- The legacy label `DAG` is displayed for `airflow_dag_run_id`; backend currently reuses this field for orchestration IDs.

## Query And Retrieval UX

Files:

- `src/components/workspace/assistant-panel.tsx`
- `src/components/query-history-page.tsx`
- `src/components/query-detail.tsx`
- `src/components/retrieval-trace.tsx`
- `src/components/history-workspace.tsx`
- `src/components/chat-workspace.tsx`

Implemented:

- Streaming RAG answers through SSE.
- Execution trace during generation.
- Query history listing at project and cross-project scope.
- Search query history.
- Filter history by answered/failed.
- Query detail with question, provider, model, cache hit, latency, persisted Markdown answer.
- Retrieval trace list with rank, document name, section/chunk, page, qdrant score, rerank score, strategy, used/not-used status, version lineage, and chunk text.
- Source selection opens supporting document route from query detail.

Limitations:

- `history-workspace.tsx` and `chat-workspace.tsx` appear to be older/specialized workspace components alongside the newer unified workspace.
- Source opening from query detail navigates to the document route with `chunk` query string, but `DocumentDetail` does not currently highlight that chunk.

## Observability

File:

- `src/components/observability-dashboard.tsx`

Implemented metrics:

- Indexed documents count.
- Successful query percentage.
- Average query latency.
- Cache hit rate.
- Recent ingestion runs.
- Recent queries.
- Failed run count in the loaded window.

Data source:

- Uses only real backend records from documents, ingestion runs, and query history.
- For global observability, `useWorkspaceOverview` fans out across owned projects.
- For project observability, direct project-scoped queries are used.

Limitations:

- No synthetic trends, charts, or estimated metrics.
- Metrics are limited to the records loaded by current endpoint limits.

## Organization And Profile

Files:

- `src/app/(dashboard)/organization/page.tsx`
- `src/app/(dashboard)/settings/profile/page.tsx`
- `src/components/app-shell.tsx`

Implemented organization UX:

- List organizations.
- Create organization.
- Rename organization.
- Delete organization with typed-name confirmation.
- Active organization indicated in list.
- Active organization switcher in the top bar updates `/auth/me`.

Implemented profile UX:

- Load current user from `/auth/me`.
- Update full name, email, organization context, and optional password.
- Avatar initials.
- Save feedback through toast.

Limitations:

- Organization delete impact preview is not available from the API, so UI warns the user to verify dependencies.

## API Endpoints Used By Frontend

| Frontend action | Backend path through `/api/backend` |
|---|---|
| Current user | `/auth/me` |
| Update profile/org context | `/auth/me` PATCH |
| Organizations | `/organizations/`, `/organizations/{id}` |
| Projects | `/projects/`, `/projects/{id}` |
| Chunker catalog | `/chunkers` |
| Documents list | `/documents/?project_id={id}` |
| Document detail | `/documents/{id}` |
| Document versions | `/documents/{id}/versions` |
| Delete document | `/documents/{id}` DELETE |
| File ingestion | `/ingest/file` |
| URL ingestion | `/ingest/url` |
| Google Drive ingestion | `/ingest/gdrive` |
| Ingestion runs | `/ingest/runs?project_id={id}&limit={n}` |
| Ingestion run detail | `/ingest/runs/{run_id}` |
| Ingestion events | `/ingest/runs/{run_id}/events` |
| Retry ingestion | `/ingest/runs/{run_id}/retry` |
| Query stream | `/rag/query/stream` |
| Query history | `/rag/projects/{project_id}/history?limit={n}` |
| Query trace | `/rag/queries/{query_log_id}` |

## Loading, Empty, Error, And Feedback States

Implemented patterns:

- `LoadingState` skeletons for page and list loading.
- `EmptyState` for projects, documents, runs, history, organizations, source inspector, retrieval evidence.
- `ErrorState` with retry for failed page loads.
- Toast success/error for mutations and stream edge cases.
- Disabled submit buttons while pending or invalid.
- Inline validation on auth and project forms.
- `aria-live` on ingestion pipeline and assistant execution trace status.
- Semantic labels and `sr-only` text for many icon/search controls.

Gaps:

- Some older areas still use `window.confirm`.
- Some compact custom popovers do not implement full focus trapping.
- Command palette footer hints keyboard navigation, but arrow-key navigation is not implemented.

## Responsive Behavior

Implemented:

- Dashboard shell collapses sidebar on desktop and uses a mobile drawer.
- Main workspace hides the knowledge panel on smaller screens and opens it as a mobile drawer.
- Assistant and document inspection share a tabbed center surface.
- Tables and lists use responsive grids or horizontal overflow where needed.
- Composer respects safe-area bottom inset.

Potential issues:

- The app has a mix of newer dark operational surfaces and older document table styling. The standalone document workspace has some lighter table classes that visually differ from the rest of the dark UI.
- The main workspace is dense and should be checked with real screenshots on narrow devices after major changes.

## Tests

| Test file | Coverage |
|---|---|
| `src/lib/api.test.ts` | API response parsing and error handling |
| `src/lib/sse.test.ts` | SSE block parsing, event IDs, error responses |
| `src/hooks/use-ingestion-stream.test.tsx` | Ingestion stream recovery behavior |
| `src/components/ingestion-card.test.tsx` | Ingestion card/pipeline rendering |
| `src/components/workspace/assistant-panel.test.tsx` | Assistant panel trace/citation behavior |
| `src/app/(dashboard)/projects/projects-page.test.tsx` | Projects page loading/empty/list behavior |
| `e2e/control-plane.spec.ts` | Browser-level control-plane flow |

Package scripts:

```bash
npm run lint
npm run test
npm run typecheck
npm run build
npm run test:e2e
```

## Current Strengths

- Secure same-origin proxy with HttpOnly session cookie.
- Strong ingestion visibility with SSE recovery and durable fallback.
- Real, backend-derived observability metrics.
- Unified project workspace covers upload, chat, citations, retrieval trace, document inspection, and document management.
- Frontend avoids inventing unavailable backend behavior.
- Good reusable UI primitives and clear status/empty/error patterns.

## Current Gaps And Cleanup Targets

- Consolidate older `DocumentsWorkspace`, `ChatWorkspace`, and `HistoryWorkspace` with the newer unified workspace direction.
- Make global `/documents` route behavior explicit and ensure it has a complete page experience.
- Add persisted initial read for sidebar collapsed state.
- Upgrade command palette to keyboard-navigable project selection.
- Replace remaining `window.confirm` delete flow with `ConfirmDeleteDialog`.
- Add focus trapping or stronger keyboard handling to custom popovers/drawers.
- Add chunk highlighting in `DocumentDetail` when opened with a `chunk` query parameter.
- Surface real per-stage durations only when backend exposes stage timestamps/durations.
- Consider exposing full extracted document preview if backend adds a content endpoint.
