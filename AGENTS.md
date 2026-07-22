# RAGForge Frontend UI/UX Redesign

## Goal

Improve the existing RAGForge frontend so it is user-friendly, responsive, accessible, and production-ready.

Preserve the current dark-green identity while improving:

- Navigation
- Typography
- Visual hierarchy
- Project CRUD
- Document management
- Ingestion visibility
- RAG chat
- Source inspection
- Query history
- Retrieval observability
- Loading and error states

The main experience must remain simple:

1. Open a project.
2. Upload documents.
3. Wait for indexing.
4. Ask questions.
5. Inspect supporting sources.

## Before implementation

Read:

- `AGENTS.md`
- `PROJECT_MAP.md`
- `frontend/src/app/`
- `frontend/src/components/`
- `frontend/src/hooks/`
- `frontend/src/lib/`

Inspect the existing implementation and identify:

- Existing reusable components
- Current API client patterns
- Current authentication handling
- Existing SSE hooks
- Existing routes
- Current tests
- Supported CRUD operations
- Missing backend capabilities

Do not begin implementation until the existing frontend structure and API surface have been inspected.

## Existing architecture to preserve

- Next.js App Router
- TypeScript
- Same-origin authenticated proxy
- HttpOnly session cookie
- FastAPI backend
- SSE ingestion recovery
- Streaming RAG answers
- Multi-tenant project isolation
- Existing typed API client
- Existing backend endpoints

## Pages in scope

Implement or optimize:

1. Sign-in
2. Registration
3. Projects
4. Create project
5. Project workspace
6. Project settings
7. Document details
8. Document version history
9. Ingestion runs
10. Ingestion run details
11. Query history
12. Query detail
13. Observability dashboard
14. Organization settings
15. User profile settings

Reuse routes that already exist. Add new frontend routes only when required.

## Global application shell

Create a consistent shell containing:

### Sidebar

- Home
- Projects
- Documents
- Ingestion Runs
- Query History
- Observability
- Organization
- Settings

The sidebar must support collapsed and expanded states.

### Top bar

- Organization switcher
- Breadcrumbs
- Global search
- Command palette trigger
- Notifications
- User menu

Do not display model selection globally when it is unrelated to the current page.

## Project CRUD

### Create

Create a project dialog or drawer containing:

- Name
- Optional description
- Default chunking strategy
- Optional advanced configuration

After creation, navigate to the new project workspace.

### Read

The projects screen must support:

- Grid and list views
- Search
- Sorting
- Loading skeletons
- Empty state
- Error state

Each project should display:

- Name
- Description
- Document count
- Current ingestion activity
- Last activity
- Project status

### Update

Support:

- Rename project
- Edit description
- Update supported project settings

Use existing backend endpoints only.

### Delete

Use a confirmation dialog.

For high-risk deletion:

- Explain affected documents and query history.
- Require the project name to be typed.
- Clearly label the action as destructive.

## Project workspace

Create a responsive three-panel workspace.

### Left panel

Knowledge source management:

- Upload area
- URL ingestion
- Google Drive ingestion
- Multimodal ingestion when available
- Chunking strategy selection
- Document search
- Status filters
- Document list
- Current ingestion summary

### Center panel

RAG chat:

- Empty-state suggestions
- User messages
- Streamed assistant messages
- Markdown rendering
- Citations
- Copy answer
- Regenerate when supported
- Feedback controls
- Selected-document context chips
- Model selector
- Retrieval settings popover
- Multiline composer

### Right panel

Context inspector tabs:

- Content
- Versions
- Knowledge Graph
- Retrieval Trace
- Metadata

The panel must be collapsible and resizable on desktop.

On smaller screens, open it as a drawer.

## Document management

Each document row must include:

- Filename
- File-type icon
- Source type
- Status
- Current version
- Updated time
- Overflow menu

Supported actions:

- Open document details
- Ask about this document
- Upload a new version
- View version history
- Retry failed ingestion
- Delete document

Do not implement direct chunk-text editing.

Do not add rollback or individual version deletion unless matching backend support exists.

## Ingestion experience

Create a visible ingestion pipeline:

1. Uploaded
2. Bronze landed
3. Parsing
4. Chunking
5. Silver completed
6. Embedding
7. Gold completed
8. Qdrant indexing
9. Indexed

Each stage should show:

- Current status
- Duration
- Start and completion timestamps when available
- Error details
- Retry information

Use SSE updates and preserve reconnect behavior.

A failed run must show:

- User-friendly explanation
- Expandable technical details
- Retry action
- Related document
- Copyable diagnostics

## Query experience

Assistant answers must include source citations.

Selecting a citation should:

1. Select the associated document.
2. Open the context panel.
3. Navigate to the source content where possible.
4. Highlight the supporting chunk.

Retrieval details should include:

- Rank
- Qdrant score
- Rerank score when present
- Retrieval strategy
- Whether the chunk was used
- Document lineage
- Version lineage
- Chunk text

## Visual design

Preserve the dark-green design language.

Use:

- Geist Sans for interface text
- Geist Mono for IDs, hashes, paths, and scores
- Clear heading hierarchy
- 8px spacing system
- Consistent control heights
- 10–12px border radii
- Restrained shadows
- Accessible contrast
- Visible keyboard focus

Avoid:

- Very large page titles
- Excessive borders
- Excessive nested cards
- Blank panels
- Tiny low-contrast text
- Unexplained technical terminology
- Decorative animations that interfere with work

## Responsive requirements

### Desktop

- Three-panel workspace
- Resizable side panels
- Persistent navigation

### Tablet

- Collapsible knowledge panel
- Inspector presented as a drawer
- Chat remains central

### Mobile

- Separate document, chat, and inspector views
- Compact navigation
- Fixed safe-area-aware composer
- Card representation for data tables
- No full-page horizontal scrolling

## Accessibility requirements

- Keyboard navigation
- Visible focus states
- Semantic buttons and links
- Form labels
- Accessible dialogs
- ARIA labels for icon-only controls
- Escape closes drawers and dialogs
- Status is not communicated by color alone
- Reduced-motion support
- Screen-reader updates for upload and ingestion progress

## Reusable components

Prefer reusable components such as:

- `AppShell`
- `Sidebar`
- `Topbar`
- `PageHeader`
- `ProjectCard`
- `ProjectForm`
- `StatusBadge`
- `EmptyState`
- `ErrorState`
- `ConfirmDeleteDialog`
- `UploadKnowledgeDrawer`
- `UploadQueue`
- `ChunkerSelector`
- `IngestionPipeline`
- `DocumentList`
- `DocumentRow`
- `DocumentInspector`
- `VersionTimeline`
- `ChatMessage`
- `ChatComposer`
- `CitationCard`
- `RetrievalTrace`
- `MetricCard`
- `QueryHistoryTable`

Do not create a single oversized workspace component.

## Constraints

- Do not change backend APIs unless a frontend requirement is impossible otherwise.
- Do not invent unsupported API fields.
- Do not weaken authentication.
- Do not expose JWTs to browser JavaScript.
- Do not break SSE streaming.
- Do not break organization and project ownership boundaries.
- Do not display fake dashboard metrics.
- Do not install a new UI framework without first verifying the current stack.
- Do not remove existing working behavior merely to simplify the redesign.

## Implementation process

1. Inspect the existing frontend.
2. Map existing components and API capabilities.
3. Identify gaps between the request and backend support.
4. Produce a concise implementation plan.
5. Implement shared design primitives first.
6. Implement the application shell.
7. Implement project CRUD.
8. Implement the project workspace.
9. Implement ingestion observability.
10. Implement query history and retrieval traces.
11. Add responsive and accessibility behavior.
12. Update tests.
13. Run validation commands.
14. Review the final diff for regressions.

## Acceptance criteria

- [ ] Existing authentication still works.
- [ ] Projects can be created, read, updated, and deleted through supported APIs.
- [ ] Documents can be listed and deleted.
- [ ] New document versions can be uploaded.
- [ ] Failed ingestion runs can be retried where supported.
- [ ] Ingestion status updates recover after refresh.
- [ ] RAG answers stream correctly.
- [ ] Citations open their supporting source.
- [ ] Query history is usable.
- [ ] Retrieval traces are inspectable.
- [ ] Every major page has loading, empty, and error states.
- [ ] The workspace works on desktop, tablet, and mobile.
- [ ] Important actions are keyboard accessible.
- [ ] No unsupported backend behavior has been invented.
- [ ] Type checking passes.
- [ ] Tests pass.
- [ ] Production build passes.

## Validation

Run the relevant commands defined by the repository, including:

```bash
npm run lint
npm run test
npm run typecheck
npm run build