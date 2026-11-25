export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code: string,
    public requestId?: string,
  ) {
    super(message);
  }
}
export async function api<T>(
  path: string,
  method = 'GET',
  body?: unknown,
  idempotencyKey?: string,
): Promise<T> {
  const headers: Record<string, string> = {
    Accept: 'application/json',
    'X-Requested-With': 'WayToGo',
  };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (method === 'POST') headers['Idempotency-Key'] = idempotencyKey ?? crypto.randomUUID();
  let response: Response;
  try {
    response = await fetch('/api/v1' + path, {
      method,
      credentials: 'same-origin',
      cache: 'no-store',
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(18000),
    });
  } catch {
    throw new ApiError('連線逾時或網路中斷，請稍後再試。', 0, 'NETWORK');
  }
  if (response.status === 204) return undefined as T;
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = data?.error ?? data?.detail ?? data;
    const message =
      typeof detail === 'string' ? detail : (detail?.message ?? '服務暫時無法連線，請稍後再試。');
    throw new ApiError(
      message,
      response.status,
      detail?.code ?? 'REQUEST_FAILED',
      data?.request_id,
    );
  }
  return data as T;
}
