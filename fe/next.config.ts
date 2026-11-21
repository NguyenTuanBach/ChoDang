import type { NextConfig } from "next";

// Địa chỉ BE (FastAPI). Chỉ dùng phía server của Next, không lộ ra trình duyệt.
const BE_URL = process.env.BE_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  // Trình duyệt gọi /api/... cùng origin với FE, Next chuyển tiếp sang BE: không vướng CORS.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${BE_URL}/api/:path*` }];
  },
};

export default nextConfig;
