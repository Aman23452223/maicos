/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    // Default to the Railway production URL so the rewrite works
    // even when NEXT_PUBLIC_API_URL is not set in Vercel. Operators
    // can override by setting NEXT_PUBLIC_API_URL to a different
    // backend (e.g. http://localhost:8000 for local dev).
    const api =
      process.env.NEXT_PUBLIC_API_URL ||
      "https://maicos-production.up.railway.app";
    return [{ source: "/api/:path*", destination: `${api}/api/:path*` }];
  },
};
export default nextConfig;
