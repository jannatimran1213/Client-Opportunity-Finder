/** @type {import('next').NextConfig} */
const nextConfig = {
  // Business search (OpenStreetMap) can take 30-60s; the dev proxy's default
  // 30s timeout returned "Internal Server Error". Allow up to 3 minutes.
  experimental: {
    proxyTimeout: 180000,
  },
  async rewrites() {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://ai-client-hunting-backend.onrender.com';
    return [
      {
        source: '/api/:path*',
        destination: `${apiUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
