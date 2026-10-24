import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Produces a small self-contained server in .next/standalone for Docker.
  output: "standalone",
  // Who's Talking? used to live at "/". Invite links sent before the move (/?join=CODE) still work.
  async redirects() {
    return [{ source: "/", has: [{ type: "query", key: "join" }], destination: "/whos-talking", permanent: false }];
  },
};

export default nextConfig;
