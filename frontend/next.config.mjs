const upstream = process.env.API_UPSTREAM || 'http://127.0.0.1:8000';
const config = {
  output: 'standalone',
  poweredByHeader: false,
  async rewrites() {
    return [
      { source: '/api/:path*', destination: upstream + '/api/:path*' },
      { source: '/ws/:path*', destination: upstream + '/ws/:path*' },
    ];
  },
};
export default config;
