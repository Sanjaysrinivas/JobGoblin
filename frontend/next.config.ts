import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Emit a minimal, self-contained server bundle for the production Docker
  // image (see frontend/Dockerfile).
  output: "standalone",
};

export default nextConfig;
