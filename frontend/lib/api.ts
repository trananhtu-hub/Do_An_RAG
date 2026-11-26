import { createBrowserSupabase } from "@/lib/supabase/client";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(message: string, code: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

export async function getAccessToken(): Promise<string | null> {
  const supabase = createBrowserSupabase();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  return session?.access_token ?? null;
}

async function parseError(response: Response): Promise<ApiError> {
  let code = `http_${response.status}`;
  let message = `Máy chủ trả về lỗi ${response.status}.`;
  try {
    const body: unknown = await response.json();
    const record = typeof body === "object" && body !== null ? (body as Record<string, unknown>) : {};
    const detail =
      typeof record.detail === "object" && record.detail !== null
        ? (record.detail as Record<string, unknown>)
        : record;
    if (typeof detail.code === "string") {
      code = detail.code;
    }
    if (typeof detail.message === "string") {
      message = detail.message;
    }
  } catch {
    // Phản hồi lỗi không phải JSON: giữ thông báo mặc định.
  }
  return new ApiError(message, code, response.status);
}

interface ApiRequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  signal?: AbortSignal;
}

export async function apiRequest<T>(
  path: string,
  { method = "GET", body, signal }: ApiRequestOptions = {},
): Promise<T> {
  const token = await getAccessToken();
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
      cache: "no-store",
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }
    throw new ApiError("Không kết nối được máy chủ.", "network_error", 0);
  }
  if (!response.ok) {
    throw await parseError(response);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export async function fetchDocumentBlob(documentId: string): Promise<Blob> {
  const token = await getAccessToken();
  const headers: Record<string, string> = {};
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  let response: Response;
  try {
    response = await fetch(`${API_URL}/documents/${documentId}/file`, {
      headers,
      cache: "no-store",
    });
  } catch {
    throw new ApiError("Không tải được tài liệu.", "network_error", 0);
  }
  if (!response.ok) {
    throw await parseError(response);
  }
  return response.blob();
}
