import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */

// In development, optionally proxy /api/v1/* to a local backend so the app
// works without a separate CORS setup. In production the frontend calls the
// API directly via NEXT_PUBLIC_API_BASE_URL (CORS handled by the backend),
// so no rewrites are emitted.
const devBackend = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig = {
  reactStrictMode: true,
  // Pin file-tracing to the frontend dir. This repo is a monorepo
  // (backend/ sibling, lockfiles at multiple levels) and without this
  // Next.js can walk up the tree during `Collecting build traces` and
  // either fail or bundle unrelated files.
  outputFileTracingRoot: __dirname,
  async rewrites() {
    if (process.env.NODE_ENV === "production") return [];
    return [
      {
        source: "/api/v1/:path*",
        destination: `${devBackend}/api/v1/:path*`,
      },
    ];
  },
};
export default nextConfig;
