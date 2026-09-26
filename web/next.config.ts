import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Self-contained server bundle for a small Docker image (ADR-0011).
  output: "standalone",
};

export default nextConfig;
