/** @type {import('next').NextConfig} */

// In development, optionally proxy /api/v1/* to a local backend so the app
// works without a separate CORS setup. In production the frontend calls the
// API directly via NEXT_PUBLIC_API_BASE_URL (CORS handled by the backend),
// so no rewrites are emitted.
const devBackend = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig = {
  reactStrictMode: true,
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
