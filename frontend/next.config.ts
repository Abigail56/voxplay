import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Produces a small self-contained server in .next/standalone for Docker.
  output: "standalone",
};

export default nextConfig;
