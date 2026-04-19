# Bifrost Tech Stack Specification

## Purpose

This document defines the approved technology stack for Bifrost Phase 1.

The goal is to:
- eliminate decision ambiguity
- prevent tool sprawl
- optimize for speed, control, and maintainability

Claude must follow this stack unless explicitly changed.

---

## Core Principles

1. Keep the stack minimal
2. Prioritize structured systems over experimental tools
3. Separate data, logic, and AI layers
4. Avoid premature scaling complexity
5. Optimize for iteration speed and clarity

---

## Phase 1 Stack Overview

### Frontend

- Framework: Next.js
- Language: TypeScript
- Styling: Tailwind CSS
- State: React state + TanStack Query

**Purpose:**
- Build command console
- Build dashboards
- Render structured responses

---

### Backend

- Framework: FastAPI
- Language: Python 3.11+
- Validation: Pydantic
- Server: Uvicorn

**Purpose:**
- API layer
- business logic
- workflow orchestration
- agent coordination

---

### Database

- Primary: PostgreSQL
- ORM: SQLAlchemy or SQLModel
- Migrations: Alembic

**Purpose:**
- system of record
- relational entity modeling
- workflow tracking

---

### AI Layer

- Provider: OpenAI API
- Pattern: task-specific calls only
- No monolithic agent loop

**Purpose:**
- drafting
- summarization
- prioritization assistance

---

### Retrieval Layer

- Storage: local or cloud file storage
- Vector DB: lightweight (FAISS or hosted option)

**Rules:**
- retrieval is secondary to structured data
- only use for approved documents

---

### Authentication

- JWT-based auth
- Local user system (Phase 1)

---

### Background Tasks

- FastAPI background tasks initially

Upgrade only if needed:
- Celery or RQ

---

## Repository Structure

```text
Bifrost/
├── frontend/
├── backend/
├── docs/
├── storage/
├── scripts/
├── .env
└── README.md