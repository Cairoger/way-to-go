import { test as base } from '@playwright/test';
import { once } from 'node:events';
import { createServer, request, type IncomingMessage, type ServerResponse } from 'node:http';
import { request as requestHttps } from 'node:https';
import type { AddressInfo } from 'node:net';

type OfflineSite = {
  origin: string;
  disconnect: () => Promise<void>;
  reconnect: () => Promise<void>;
  handleApi: (handler: (req: IncomingMessage, res: ServerResponse) => Promise<void>) => void;
};

// Give each test a real origin that can disappear while the service worker remains installed.
// Stopping this listener also disconnects requests made by a worker or a newly opened tab.
export const test = base.extend<{ offlineSite: OfflineSite }>({
  offlineSite: async ({ baseURL }, runTest) => {
    const upstream = new URL(baseURL!);
    const send = upstream.protocol === 'https:' ? requestHttps : request;
    let apiHandler: Parameters<OfflineSite['handleApi']>[0] | undefined;
    let port = 0;
    const server = createServer((req, res) => {
      if (apiHandler && req.url?.startsWith('/api/v1/')) {
        void apiHandler(req, res).catch((error) => res.destroy(error));
        return;
      }
      const headers = { ...req.headers, host: upstream.host };
      if (headers.origin === 'http://127.0.0.1:' + port) headers.origin = upstream.origin;
      const forwarded = send(upstream, { method: req.method, path: req.url, headers }, (reply) => {
        res.writeHead(reply.statusCode!, reply.headers);
        reply.pipe(res);
      });
      forwarded.on('error', (error) => res.destroy(error));
      res.on('close', () => forwarded.destroy());
      req.pipe(forwarded);
    });
    async function reconnect() {
      server.listen(port, '127.0.0.1');
      await once(server, 'listening');
      port = (server.address() as AddressInfo).port;
    }
    async function disconnect() {
      if (!server.listening) return;
      const closed = once(server, 'close');
      server.close();
      server.closeAllConnections();
      await closed;
    }
    await reconnect();
    try {
      await runTest({
        origin: 'http://127.0.0.1:' + port,
        reconnect,
        disconnect,
        handleApi: (handler) => {
          apiHandler = handler;
        },
      });
    } finally {
      await disconnect();
    }
  },
});

export type { OfflineSite };
