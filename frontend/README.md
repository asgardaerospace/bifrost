# Bifrost Frontend

Next.js 14 (App Router) · TypeScript · Tailwind CSS · TanStack Query.

## Layout

```
frontend/
├── app/
│   ├── layout.tsx           # root shell + nav + providers
│   ├── providers.tsx        # TanStack Query client
│   ├── globals.css          # tailwind + theme
│   ├── page.tsx             # redirects to /dashboard
│   ├── dashboard/page.tsx   # executive dashboard
│   └── console/page.tsx     # command console
├── components/
│   ├── nav.tsx
│   ├── ui.tsx               # Panel, Pill, Stat, Empty, date helpers
│   ├── command-console/
│   │   ├── command-input.tsx
│   │   └── command-history.tsx
│   └── outputs/
│       ├── response-renderer.tsx
│       ├── summary-output.tsx
│       ├── ranked-output.tsx
│       ├── draft-output.tsx
│       ├── review-output.tsx
│       ├── workflow-output.tsx
│       ├── clarification-output.tsx
│       └── unsupported-output.tsx
├── lib/api.ts               # typed fetch client
├── types/api.ts             # TS mirrors of backend schemas
├── package.json
├── tsconfig.json
├── tailwind.config.ts
├── postcss.config.mjs
├── next.config.mjs
└── .env.local.example
```

## Setup

```bash
cd frontend
cp .env.local.example .env.local
# edit NEXT_PUBLIC_API_BASE_URL if your backend isn't on localhost:8000

npm install
npm run dev
```

Open http://localhost:3000 → redirects to `/dashboard`.

## Connecting to the backend

1. Start Postgres + the backend first:
   ```bash
   cd ../backend
   uvicorn app.main:app --reload --port 8000
   ```
2. Ensure `NEXT_PUBLIC_API_BASE_URL` points at it (default: `http://localhost:8000/api/v1`).
3. CORS: the backend reads `CORS_ORIGINS` from `.env`. Include
   `http://localhost:3000` there before starting the server.

## Pages

- **Dashboard** (`/dashboard`) — stats + pipeline-by-stage + top priority +
  overdue + stale + pending approvals + recent activity.
- **Command Console** (`/console`) — text command input, structured response
  rendering, recent command history.

All response types from `POST /command-console/commands` are rendered by
`ResponseRenderer`, which dispatches to typed components by `output_type`.
No free-text blobs.
