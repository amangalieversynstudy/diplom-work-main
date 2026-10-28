/** @type {import('next').NextConfig} */
const nextConfig = {
  eslint: {
    ignoreDuringBuilds: true,
  },
  // a self-contained server for the Docker image (frontend/Dockerfile); Vercel builds as before
  output: "standalone",
  poweredByHeader: false,
};

module.exports = nextConfig;
