import type { AuthSession } from "./types";

export const authStorageKey = "loreforge.auth.session";

export function readStoredAuthSession(storage: Storage = window.sessionStorage): AuthSession | null {
  const rawValue = storage.getItem(authStorageKey);
  if (!rawValue) {
    return null;
  }

  try {
    const parsedValue = JSON.parse(rawValue) as Partial<AuthSession>;
    if (
      typeof parsedValue.apiKey === "string" &&
      parsedValue.apiKey.trim() &&
      typeof parsedValue.label === "string" &&
      parsedValue.label.trim()
    ) {
      return {
        apiKey: parsedValue.apiKey,
        label: parsedValue.label,
      };
    }
  } catch {
    removeStoredAuthSession(storage);
  }

  return null;
}

export function writeStoredAuthSession(
  session: AuthSession,
  storage: Storage = window.sessionStorage,
): void {
  storage.setItem(authStorageKey, JSON.stringify(session));
}

export function removeStoredAuthSession(storage: Storage = window.sessionStorage): void {
  storage.removeItem(authStorageKey);
}
