"use client";

import { createBrowserClient } from "@supabase/ssr";
import type { SupabaseClient } from "@supabase/supabase-js";

import { supabaseBaseUrl } from "./url";

let cached: SupabaseClient | null = null;

export function createBrowserSupabase(): SupabaseClient {
  if (cached) {
    return cached;
  }
  const url = supabaseBaseUrl(process.env.NEXT_PUBLIC_SUPABASE_URL);
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !key) {
    throw new Error("Thiếu cấu hình Supabase cho trình duyệt.");
  }
  cached = createBrowserClient(url, key);
  return cached;
}
