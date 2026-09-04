import type { NextConfig } from "next";

// Vercel evaluates rewrites at build time.  The public variable is the
// deployment contract; BACKEND_URL remains available for Docker and local use.
const backendUrl =
  process.env.NEXT_PUBLIC_API_URL ?? process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backendUrl}/:path*` }];
  }
};

export default nextConfig;
