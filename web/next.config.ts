import type { NextConfig } from "next";

const BACKEND_INTERNAL_URL =
  process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000";

// Rewrite /api/* and /_internal_backend/* to the backend so the browser can
// reach it without CORS. This is what makes a single tunnel (cpolar / ngrok
// / Cloudflare Tunnel) on :3000 work end-to-end — same origin for both
// pages and API calls. In normal split-host deployment (Vercel + Fly) the
// frontend can leave the rewrite enabled, it just won't match.
const nextConfig: NextConfig = {
  reactStrictMode: true,
  typedRoutes: true,
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${BACKEND_INTERNAL_URL}/api/:path*` },
    ];
  },
};

export default nextConfig;
