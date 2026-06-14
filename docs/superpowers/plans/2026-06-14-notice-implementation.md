# Notice Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the system-internal notice center described in `docs/superpowers/specs/2026-06-14-notice-design.md`.

**Architecture:** Add a persisted `notices` domain in the FastAPI backend with rule-based generation before reads. The React frontend consumes notice list and summary APIs, renders `/notice`, and updates notification state through mutations.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, pytest, React, React Router, React Query, Vite, lucide-react.

---

## File Structure

- Create `backend/app/models/notice.py`: SQLAlchemy `Notice` table.
- Create `backend/app/schemas/notice.py`: Pydantic API response schemas.
- Create `backend/app/repositories/notice_repository.py`: notice persistence operations.
- Create `backend/app/services/notice_service.py`: rule generation, grouping, formatting, target URL mapping, state transitions.
- Create `backend/app/api/notice.py`: `/api/notices` routes.
- Modify `backend/app/main.py`: import notice model and include notice router.
- Create `backend/tests/test_api_notice.py`: API and rule-generation tests.
- Create `frontend/src/api/notices.ts`: typed fetch helpers.
- Create `frontend/src/pages/NoticePage.tsx`: notice center UI.
- Modify `frontend/src/main.tsx`: add `/notice` route.
- Modify `frontend/src/components/AppShell.tsx`: make notice nav link active and show API-driven unread badge.
- Modify `frontend/src/styles.css`: notice page styles aligned to prototype.

## Task 1: Backend Notice Domain

**Files:**
- Create: `backend/tests/test_api_notice.py`
- Create: `backend/app/models/notice.py`
- Create: `backend/app/schemas/notice.py`
- Create: `backend/app/repositories/notice_repository.py`
- Create: `backend/app/services/notice_service.py`
- Create: `backend/app/api/notice.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write failing backend API tests**

Create `backend/tests/test_api_notice.py` with tests for welcome generation, report-ready generation, high blood pressure alert, category filtering, state mutations, summary count, and de-duplication.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_api_notice.py -v`

Expected: import or 404 failures because notice API does not exist.

- [ ] **Step 3: Implement notice model and schemas**

Add SQLAlchemy `Notice` and Pydantic response models matching the design document.

- [ ] **Step 4: Implement repository**

Add create/list/count/update/read-all methods, with `dedupe_key` checks.

- [ ] **Step 5: Implement service rules and grouping**

Generate welcome, report-ready, blood-pressure alert/improvement, report reminder, and recommendation notices from existing tables.

- [ ] **Step 6: Implement API routes and app registration**

Expose:

```text
GET  /api/notices
GET  /api/notices/summary
POST /api/notices/{notice_id}/read
POST /api/notices/read-all
POST /api/notices/{notice_id}/snooze
POST /api/notices/{notice_id}/done
```

- [ ] **Step 7: Run backend notice tests**

Run: `cd backend && pytest tests/test_api_notice.py -v`

Expected: all tests pass.

## Task 2: Frontend Notice UI

**Files:**
- Create: `frontend/src/api/notices.ts`
- Create: `frontend/src/pages/NoticePage.tsx`
- Modify: `frontend/src/main.tsx`
- Modify: `frontend/src/components/AppShell.tsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Add notice API client**

Create typed fetch helpers for list, summary, read, read-all, snooze, and done.

- [ ] **Step 2: Add NoticePage**

Render filters, grouped notice cards, and action buttons using React Query.

- [ ] **Step 3: Wire routing and app shell**

Add `/notice` route and make notification nav link route to `/notice`. Show unread badge from `/api/notices/summary`.

- [ ] **Step 4: Add CSS**

Add `.notice-*` styles aligned with `prd/prototype/notice.html`.

- [ ] **Step 5: Run frontend build**

Run: `cd frontend && npm run build`

Expected: build succeeds.

## Task 3: Final Verification

**Files:**
- Verify all modified files.

- [ ] **Step 1: Run focused backend tests**

Run: `cd backend && pytest tests/test_api_notice.py tests/test_api_device.py -v`

Expected: all tests pass.

- [ ] **Step 2: Run frontend build**

Run: `cd frontend && npm run build`

Expected: build succeeds.

- [ ] **Step 3: Review git diff**

Run: `git diff -- backend/app frontend/src docs/superpowers`

Expected: diff only contains notice implementation plus the notice spec/plan.

