export function supabaseBaseUrl(raw: string | undefined): string {
  const value = (raw ?? "").trim();
  if (!value) {
    return "";
  }
  try {
    return new URL(value).origin;
  } catch {
    return "";
  }
}
