# PDF KB Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the PDF report knowledge-base feature from `docs/superpowers/specs/2026-06-12-pdf-kb-design.md` with separated backend and frontend directories.

**Architecture:** The backend exposes FastAPI endpoints for PDF upload, document listing/detail, and vector search. MySQL stores document/page/chunk records; Milvus stores chunk vectors. The frontend is a React/Vite app styled after `prd/prototype/reports.html`.

**Tech Stack:** FastAPI, SQLAlchemy, PyMuPDF, pymilvus, MySQL, React, TypeScript, Vite, Tailwind CSS, TanStack Query, React Router, lucide-react.

---

## File Structure

- `backend/app/main.py`: FastAPI app factory and router registration.
- `backend/app/api/kb.py`: KB HTTP endpoints.
- `backend/app/core/config.py`: environment-driven settings.
- `backend/app/db/session.py`: SQLAlchemy engine/session setup.
- `backend/app/models/kb.py`: MySQL ORM models.
- `backend/app/schemas/kb.py`: Pydantic request/response models.
- `backend/app/services/pdf_extractor.py`: PDF text extraction.
- `backend/app/services/chunker.py`: text chunking.
- `backend/app/services/metadata.py`: simple metadata extraction.
- `backend/app/services/embedding.py`: deterministic local embedding adapter plus optional external adapter seam.
- `backend/app/services/vector_store.py`: Milvus adapter and in-memory test adapter.
- `backend/app/services/kb_service.py`: synchronous upload and search workflow.
- `backend/tests/`: backend unit tests.
- `frontend/`: Vite React app.
- `frontend/src/api/kb.ts`: frontend API client.
- `frontend/src/components/`: report UI components.
- `frontend/src/pages/`: report list/detail pages.

## Tasks

- [x] Backend core tests and pure services: chunking, metadata extraction, deterministic embedding, PDF text extraction failure behavior.
- [x] Backend persistence and API: SQLAlchemy models, FastAPI routes, synchronous upload/search flow, MySQL/Milvus adapters.
- [x] Frontend scaffold and UI: React/Vite/Tailwind app, reports grid based on prototype, upload dialog, search panel, detail page.
- [x] Verification: run backend tests, frontend build, and API import checks.
