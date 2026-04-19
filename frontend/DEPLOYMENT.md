# Bifrost Frontend — Vercel Deployment

Production target: **https://bifrost.asgardaerospace.com**
Backend API (separate service): **https://api.bifrost.asgardaerospace.com/api/v1**

The frontend is a standard Next.js 14 App Router app. It is a pure client of
the backend — it does not bundle any backend logic, and in production it calls
the API over HTTPS on a separate subdomain. CORS is enforced by the backend.

---

## 1. Environment variables (Vercel → Project Settings → Environment Variables)

Required, for Production, Preview, and Development environments:

| Name                       | Value                                                |
| -------------------------- | ---------------------------------------------------- |
| `NEXT_PUBLIC_API_BASE_URL` | `https://api.bifrost.asgardaerospace.com/api/v1`     |

Notes:
- Variable must be prefixed `NEXT_PUBLIC_` so it is inlined into the client bundle.
- Must include the `/api/v1` suffix.
- Trailing slashes are tolerated (stripped at runtime).
- If unset in production, the app renders a visible red banner and all API
  calls fail fast with a clear error — it does **not** silently fall back to
  `localhost`.

Also required on the **backend** side (not here): `CORS_ORIGINS` must include
`https://bifrost.asgardaerospace.com`.

---

## 2. Deploy to Vercel

1. In Vercel, **New Project → Import Git Repository** and select the Bifrost repo.
2. In the import screen:
   - **Root Directory**: `frontend`
   - **Framework Preset**: Next.js (auto-detected)
   - **Build Command**: `next build` (default)
   - **Install Command**: `npm install` (default)
   - **Output Directory**: leave blank (Next.js default `.next`)
3. Under **Environment Variables**, add `NEXT_PUBLIC_API_BASE_URL` as above
   for Production + Preview + Development.
4. Click **Deploy**. First deploy will be served at the auto-assigned
   `*.vercel.app` URL.

No `vercel.json` is needed — the Next.js preset handles App Router routing,
static assets, and image optimization out of the box.

---

## 3. Attach the custom domain `bifrost.asgardaerospace.com`

In Vercel → Project → **Settings → Domains**:

1. Add domain: `bifrost.asgardaerospace.com`.
2. Vercel will show the DNS record it needs.

On the DNS provider for `asgardaerospace.com`, add:

| Type    | Host / Name | Value                 | TTL   |
| ------- | ----------- | --------------------- | ----- |
| `CNAME` | `bifrost`   | `cname.vercel-dns.com`| 300   |

(Some DNS providers require the apex form — if so, use the exact target Vercel
shows in the Domains tab; it supersedes this table.)

Once DNS propagates (usually minutes), Vercel auto-issues a Let's Encrypt TLS
certificate. The domain will show **Valid Configuration** in the dashboard.

---

## 4. Backend (separate service)

The backend is not deployed to Vercel. It is deployed independently at
`api.bifrost.asgardaerospace.com` (point DNS A/AAAA/CNAME at the backend host
/ load balancer per the backend deployment guide).

Backend must have in its environment:

```
CORS_ORIGINS=https://bifrost.asgardaerospace.com
```

(Plus any additional preview/dev origins as needed.)

---

## 5. Post-deploy verification checklist

After DNS is live and the deployment is green:

- [ ] `https://bifrost.asgardaerospace.com` loads and redirects/renders the workspace.
- [ ] Browser DevTools → Network shows API calls going to
      `https://api.bifrost.asgardaerospace.com/api/v1/...` (no `localhost`, no `127.0.0.1`).
- [ ] No red "API is not configured" banner at the top of the page.
- [ ] Executive briefing renders in the left column (or shows a
      section-scoped error with a retry button if backend is down —
      the rest of the UI must still render).
- [ ] Command console (bottom bar) accepts input and returns a response.
- [ ] `/dashboard` loads with cards populated; individual cards that fail
      show `—` / empty state rather than crashing the page.
- [ ] Temporarily block the API (e.g. via browser devtools request blocking)
      and confirm: banner is not shown (URL is still configured), but each
      section shows its own error state; the app does not go blank.
- [ ] TLS cert is valid (padlock, no mixed-content warnings).
