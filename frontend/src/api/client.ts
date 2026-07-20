export type ApiClientOptions = {
  baseUrl: string;
  fetchImpl?: typeof fetch;
  getAuthToken?: () => string | null | undefined;
  onUnauthorized?: () => void;
  timeoutMs?: number;
};

export type ApiRequestOptions = {
  body?: unknown;
  headers?: HeadersInit;
  method?: string;
  signal?: AbortSignal;
};

export type ApiClient = {
  request: <TResponse>(path: string, options?: ApiRequestOptions) => Promise<TResponse>;
};

export class ApiClientError extends Error {
  readonly detail: unknown;
  readonly requestId: string | null;
  readonly status: number;

  constructor(message: string, options: { status: number; detail: unknown; requestId: string | null }) {
    super(message);
    this.name = "ApiClientError";
    this.detail = options.detail;
    this.requestId = options.requestId;
    this.status = options.status;
  }
}

export class UnauthorizedApiError extends ApiClientError {
  constructor(options: { detail: unknown; requestId: string | null }) {
    super("Authentication is required.", {
      detail: options.detail,
      requestId: options.requestId,
      status: 401,
    });
    this.name = "UnauthorizedApiError";
  }
}

export class ForbiddenApiError extends ApiClientError {
  constructor(options: { detail: unknown; requestId: string | null }) {
    super("Access is forbidden.", {
      detail: options.detail,
      requestId: options.requestId,
      status: 403,
    });
    this.name = "ForbiddenApiError";
  }
}

const defaultTimeoutMs = 15000;

export function createApiClient({
  baseUrl,
  fetchImpl = fetch,
  getAuthToken,
  onUnauthorized,
  timeoutMs = defaultTimeoutMs,
}: ApiClientOptions): ApiClient {
  const normalizedBaseUrl = baseUrl.replace(/\/+$/, "");

  async function request<TResponse>(path: string, options: ApiRequestOptions = {}): Promise<TResponse> {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
    const headers = new Headers(options.headers);
    headers.set("Accept", "application/json");

    const token = getAuthToken?.();
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }

    let body: BodyInit | undefined;
    if (options.body instanceof FormData) {
      body = options.body;
    } else if (options.body !== undefined) {
      headers.set("Content-Type", "application/json");
      body = JSON.stringify(options.body);
    }

    const signal = composeAbortSignal(options.signal, controller.signal);

    try {
      const response = await fetchImpl(`${normalizedBaseUrl}${path}`, {
        body,
        headers,
        method: options.method ?? "GET",
        signal,
      });
      const requestId = response.headers.get("X-Request-ID");
      const payload = await readPayload(response);

      if (!response.ok) {
        if (response.status === 401) {
          onUnauthorized?.();
          throw new UnauthorizedApiError({ detail: payload, requestId });
        }
        if (response.status === 403) {
          throw new ForbiddenApiError({ detail: payload, requestId });
        }
        throw new ApiClientError("API request failed.", {
          detail: payload,
          requestId,
          status: response.status,
        });
      }

      return payload as TResponse;
    } finally {
      window.clearTimeout(timeout);
    }
  }

  return { request };
}

function composeAbortSignal(primary: AbortSignal | undefined, secondary: AbortSignal): AbortSignal {
  if (!primary) {
    return secondary;
  }

  const controller = new AbortController();
  const abort = () => controller.abort();
  primary.addEventListener("abort", abort, { once: true });
  secondary.addEventListener("abort", abort, { once: true });
  return controller.signal;
}

async function readPayload(response: Response): Promise<unknown> {
  const contentType = response.headers.get("Content-Type") ?? "";
  if (response.status === 204) {
    return undefined;
  }
  if (contentType.includes("application/json")) {
    return response.json();
  }
  return response.text();
}
