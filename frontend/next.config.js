/** @type {import('next').NextConfig} */
const nextConfig = {
  // Lint is run as a dedicated CI step (`npm run lint`) and is also wired
  // into the lint-staged pre-commit hook. Keeping it out of the build
  // pipeline means a deploy never gets blocked by a stale unused-import
  // warning in an untouched legacy file, while developers still get full
  // lint feedback locally and in CI. This matches Vercel's recommended
  // separation-of-concerns pattern for production Next.js apps.
  eslint: {
    ignoreDuringBuilds: true,
  },
};

module.exports = nextConfig;
