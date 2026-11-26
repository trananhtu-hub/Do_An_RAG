"use client";

import { useMemo, useSyncExternalStore } from "react";

import type { Preferences } from "@/lib/types";

const STORAGE_KEY = "saa-rag-preferences";
const CHANGE_EVENT = "saa-rag-preferences-changed";

export const DEFAULT_PREFERENCES: Preferences = {
  mode: "step_by_step",
  language: "vi",
  model: "",
};

const DEFAULT_SNAPSHOT = JSON.stringify(DEFAULT_PREFERENCES);

export function parsePreferences(raw: string): Preferences {
  try {
    const parsed = JSON.parse(raw) as Partial<Preferences>;
    return {
      mode: parsed.mode === "fast" ? "fast" : "step_by_step",
      language: parsed.language === "en" ? "en" : "vi",
      model: typeof parsed.model === "string" ? parsed.model : "",
    };
  } catch {
    return DEFAULT_PREFERENCES;
  }
}

export function getPreferencesSnapshot(): string {
  if (typeof window === "undefined") {
    return DEFAULT_SNAPSHOT;
  }
  try {
    return window.localStorage.getItem(STORAGE_KEY) ?? DEFAULT_SNAPSHOT;
  } catch {
    return DEFAULT_SNAPSHOT;
  }
}

export function subscribePreferences(onStoreChange: () => void): () => void {
  if (typeof window === "undefined") {
    return () => {};
  }
  window.addEventListener(CHANGE_EVENT, onStoreChange);
  window.addEventListener("storage", onStoreChange);
  return () => {
    window.removeEventListener(CHANGE_EVENT, onStoreChange);
    window.removeEventListener("storage", onStoreChange);
  };
}

export function usePreferences(): Preferences {
  const raw = useSyncExternalStore(
    subscribePreferences,
    getPreferencesSnapshot,
    () => DEFAULT_SNAPSHOT,
  );
  return useMemo(() => parsePreferences(raw), [raw]);
}

export function savePreferences(preferences: Preferences): void {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences));
  window.dispatchEvent(new CustomEvent(CHANGE_EVENT));
}

export function clearPreferences(): void {
  window.localStorage.removeItem(STORAGE_KEY);
  window.dispatchEvent(new CustomEvent(CHANGE_EVENT));
}
