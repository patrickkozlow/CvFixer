# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Resume Matcher is an AI-powered application for tailoring resumes to job descriptions. It runs locally with Ollama or connects to cloud LLM providers via LiteLLM.

| Layer | Stack |
|-------|-------|
| **Backend** | FastAPI + Python 3.13+, LiteLLM (multi-provider AI) |
| **Frontend** | Next.js 16 + React 19, Tailwind CSS v4 |
| **Database** | TinyDB (JSON file storage) |
| **PDF** | Headless Chromium via Playwright |

---

## Commands

```bash
# Install all dependencies (frontend npm + backend uv sync)
npm run install

# Development (both servers concurrently)
npm run dev

# Individual servers
npm run dev:backend   # FastAPI on :8000
npm run dev:frontend  # Next.js on :3000 (uses Turbopack)

# Quality checks (run before committing)
npm run lint          # ESLint frontend
npm run format        # Prettier frontend

# Tests
cd apps/frontend && npm run test    # Vitest (jsdom)
cd apps/backend && uv run pytest    # pytest

# Build
npm run build
```

Backend dependencies are managed with `uv` (pyproject.toml at `apps/backend/`). Frontend dependencies use npm (`apps/frontend/package.json`). There is no root-level monorepo tool (no turborepo/nx); the root package.json just orchestrates npm scripts.

---

## Architecture

### Data Flow: Resume Tailoring (Core Feature)

The core workflow is a **preview-confirm** pattern:

1. User uploads resume (PDF/DOCX) → `POST /api/v1/resumes/upload` → parsed to Markdown → structured JSON → stored in TinyDB as "master"
2. User submits job description → `POST /api/v1/jobs/upload` → stored with extracted keywords
3. User initiates tailoring → `POST /api/v1/resumes/improve/preview` (read-only preview) or `/confirm` (creates record)
4. Backend pipeline: `improver.py` extracts job keywords → generates improved resume → `refiner.py` runs multi-pass refinement:
   - Pass 1: Keyword injection (missing JD skills)
   - Pass 2: AI phrase removal (blacklist in `prompts/refinement.py`)
   - Pass 3: Alignment validation against master resume (no fabrication)
5. Cover letter + outreach message generated in parallel (`asyncio.gather`)
6. Tailored resume stored with `parent_id` linking back to master

### Frontend API Client

`apps/frontend/lib/api/client.ts` provides typed utilities (`apiFetch`, `apiPost`, `apiPut`, `apiDelete`). All calls go through `NEXT_PUBLIC_API_URL` (defaults to `http://localhost:8000`) with `/api/v1` prefix. Domain-specific functions in `resume.ts`, `enrichment.ts`, `config.ts`.

### Frontend State Management

No global state library. Complex workflows use `useReducer` with typed action dispatches (see `hooks/use-enrichment-wizard.ts` for the pattern: multi-step state machine with START_ANALYSIS → QUESTIONS → GENERATION → PREVIEW → APPLY).

### Backend Service Layer

Routers (`app/routers/`) handle HTTP concerns only. Business logic lives in services (`app/services/`): `improver.py` (tailoring), `refiner.py` (multi-pass refinement), `parser.py` (PDF/DOCX parsing), `cover_letter.py` (generation).

### LLM Integration

`app/llm.py` wraps LiteLLM with provider-specific configuration. Key behaviors:
- JSON mode auto-enabled for supported models (explicit allowlist of JSON-safe models)
- Timeouts: 30s health, 120s completion, 180s JSON
- 2 retries with lower temperature on failure
- API keys passed directly via `api_key` parameter (not env vars)
- Prompt injection sanitization on all user inputs
- Job descriptions truncated to 2000 chars with warning

### Database

TinyDB with three tables: `resumes` (with `is_master`/`parent_id` for master→tailored relationships, `processing_status` for async state), `jobs` (with cached `job_keywords` and `preview_hashes`), `improvements` (linking resume + job + improvement list). Lazy-initialized singleton.

### Custom Sections System

Resume sections are dynamically typed: `personalInfo` (always first), `text` (single block), `itemList` (title/subtitle/years/description), `stringList` (simple array). Users can rename, reorder, hide, delete, and add custom sections.

### i18n

Supported locales: `en`, `es`, `zh`, `ja`. UI translations in `apps/frontend/messages/`. Content language sent to backend for LLM-generated output. Use `useTranslations()` hook from `@/lib/i18n`.

---

## Non-Negotiable Rules

1. **All frontend UI changes** MUST follow [Swiss International Style](../docs/agent/design/style-guide.md)
2. **All Python functions** MUST have type hints
3. **Run `npm run lint` and `npm run format`** before committing frontend changes
4. **Log detailed errors server-side**, return generic messages to clients
5. **Do NOT modify** `.github/workflows/` files without explicit request
6. **Do NOT modify** CI/CD configuration, Docker build behavior, or disable existing tests without explicit request

---

## Code Patterns

### Backend Error Handling
```python
except Exception as e:
    logger.error(f"Operation failed: {e}")
    raise HTTPException(status_code=500, detail="Operation failed. Please try again.")
```

### Frontend Textarea Fix
All textareas need Enter key handling to prevent form submission:
```tsx
const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
  if (e.key === 'Enter') e.stopPropagation();
};
```

### Mutable Defaults (Python)
Always use `copy.deepcopy()` for mutable defaults — shared state bugs are a known issue:
```python
import copy
data = copy.deepcopy(DEFAULT_DATA)
```

---

## Design System Quick Reference

| Element | Value |
|---------|-------|
| Canvas background | `#F0F0E8` |
| Ink (text) | `#000000` |
| Hyper Blue (links) | `#1D4ED8` |
| Signal Green (success) | `#15803D` |
| Alert Orange (warning) | `#F97316` |
| Alert Red (error) | `#DC2626` |
| Headers font | `font-serif` |
| Body font | `font-sans` |
| Metadata font | `font-mono` |
| Borders | `rounded-none`, 1px black, hard shadows |

---

## Documentation Index

| Area | Document |
|------|----------|
| Backend architecture | [backend-guide.md](../docs/agent/architecture/backend-guide.md) |
| Frontend workflow | [frontend-workflow.md](../docs/agent/architecture/frontend-workflow.md) |
| API contracts | [front-end-apis.md](../docs/agent/apis/front-end-apis.md) |
| Style guide (required) | [style-guide.md](../docs/agent/design/style-guide.md) |
| PDF templates | [pdf-template-guide.md](../docs/agent/design/pdf-template-guide.md) |
| Custom sections | [custom-sections.md](../docs/agent/features/custom-sections.md) |
| i18n | [i18n.md](../docs/agent/features/i18n.md) |
| LLM integration | [llm-integration.md](../docs/agent/llm-integration.md) |
| Coding standards | [coding-standards.md](../docs/agent/coding-standards.md) |
