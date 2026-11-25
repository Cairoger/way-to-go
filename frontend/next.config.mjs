const upstream = process.env.API_UPSTREAM || 'http://127.0.0.1:8000';
const config = {
  output: 'standalone',
  experimental: { proxyClientMaxBodySize: process.env.PROXY_UPLOAD_LIMIT || '110mb' },
  poweredByHeader: false,
  async rewrites() {
    return [
      { source: '/api/:path*', destination: upstream + '/api/:path*' },
      { source: '/ws/:path*', destination: upstream + '/ws/:path*' },
    ];
  },
};
export default config;
