import type { NextConfig } from "next";

const apiUpstream = process.env.SVR_API_UPSTREAM || "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  experimental: {
    optimizePackageImports: ["@tabler/icons-react"],
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${apiUpstream}/api/:path*`,
      },
    ];
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Permissions-Policy",
            value: "camera=(), geolocation=(), microphone=(self)",
          },
          {
            key: "Content-Security-Policy",
            value:
              "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; media-src 'self' blob:; connect-src 'self' http://127.0.0.1:8000 http://localhost:8000 ws://127.0.0.1:8000 ws://localhost:8000 ws: wss:; frame-ancestors 'none';",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
