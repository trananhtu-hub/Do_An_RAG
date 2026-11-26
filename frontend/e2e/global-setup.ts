import { randomBytes } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";

const REPO_ROOT = resolve(__dirname, "..", "..");
const CREDENTIALS_PATH = resolve(__dirname, ".auth", "credentials.json");
const DEFAULT_EMAIL = "saa-e2e@example.com";

interface TestCredentials {
  email: string;
  password: string;
}

function readEnvFile(path: string): Record<string, string> {
  const values: Record<string, string> = {};
  for (const line of readFileSync(path, "utf8").split(/\r?\n/)) {
    if (!line.trim() || line.trimStart().startsWith("#")) {
      continue;
    }
    const match = /^\s*([A-Za-z0-9_]+)\s*=\s*(.*?)\s*$/.exec(line);
    if (!match) {
      continue;
    }
    values[match[1]] = match[2].replace(/^(['"])(.*)\1$/, "$2");
  }
  return values;
}

function readCredentials(): TestCredentials {
  if (existsSync(CREDENTIALS_PATH)) {
    try {
      const parsed = JSON.parse(readFileSync(CREDENTIALS_PATH, "utf8")) as TestCredentials;
      if (parsed.email && parsed.password) {
        return parsed;
      }
    } catch {
      // Tệp hỏng: tạo tài khoản mới bên dưới.
    }
  }
  return {
    email: process.env.E2E_EMAIL ?? DEFAULT_EMAIL,
    password: randomBytes(18).toString("base64url"),
  };
}

async function readErrorCode(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as Record<string, unknown>;
    for (const candidate of [
      body.error_code,
      body.code,
      body.msg,
      body.message,
      body.error,
      body.error_description,
    ]) {
      if (typeof candidate === "string") {
        return candidate;
      }
    }
    return `http_${response.status}`;
  } catch {
    return `http_${response.status}`;
  }
}

async function ensureUser(
  supabaseUrl: string,
  serviceKey: string,
  credentials: TestCredentials,
): Promise<void> {
  const headers = {
    apikey: serviceKey,
    Authorization: `Bearer ${serviceKey}`,
    "Content-Type": "application/json",
  };

  const createResponse = await fetch(`${supabaseUrl}/auth/v1/admin/users`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      email: credentials.email,
      password: credentials.password,
      email_confirm: true,
    }),
  });
  if (createResponse.ok) {
    return;
  }

  const code = await readErrorCode(createResponse);
  if (!/exist|registered|duplicate/i.test(code)) {
    throw new Error(`Không tạo được tài khoản E2E (${code}).`);
  }

  const listResponse = await fetch(
    `${supabaseUrl}/auth/v1/admin/users?page=1&per_page=1000`,
    { headers },
  );
  if (!listResponse.ok) {
    throw new Error(`Không liệt kê được người dùng Supabase (HTTP ${listResponse.status}).`);
  }
  const listing = (await listResponse.json()) as { users?: Array<{ id?: string; email?: string }> };
  const existing = listing.users?.find(
    (user) => user.email?.toLowerCase() === credentials.email.toLowerCase(),
  );
  if (!existing?.id) {
    throw new Error("Tài khoản E2E đã tồn tại nhưng không tìm thấy trong danh sách người dùng.");
  }

  const updateResponse = await fetch(`${supabaseUrl}/auth/v1/admin/users/${existing.id}`, {
    method: "PUT",
    headers,
    body: JSON.stringify({ password: credentials.password, email_confirm: true }),
  });
  if (!updateResponse.ok) {
    throw new Error(`Không đặt lại được mật khẩu tài khoản E2E (HTTP ${updateResponse.status}).`);
  }
}

function supabaseOrigin(raw: string | undefined): string {
  try {
    return raw ? new URL(raw).origin : "";
  } catch {
    return "";
  }
}

export default async function globalSetup(): Promise<void> {
  const env = readEnvFile(resolve(REPO_ROOT, ".env"));
  const supabaseUrl = supabaseOrigin(env.SUPABASE_URL);
  const serviceKey = env.SUPABASE_SERVICE_ROLE_KEY;
  if (!supabaseUrl || !serviceKey) {
    throw new Error(
      "Thiếu SUPABASE_URL hoặc SUPABASE_SERVICE_ROLE_KEY trong .env để tạo tài khoản E2E.",
    );
  }

  const credentials = readCredentials();
  await ensureUser(supabaseUrl, serviceKey, credentials);

  mkdirSync(dirname(CREDENTIALS_PATH), { recursive: true });
  writeFileSync(CREDENTIALS_PATH, JSON.stringify(credentials, null, 2), "utf8");
}
