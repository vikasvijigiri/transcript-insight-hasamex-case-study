import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Produces a minimal self-contained server bundle in .next/standalone,
  // which the production Dockerfile copies instead of shipping node_modules.
  output: "standalone",
};

export default nextConfig;
