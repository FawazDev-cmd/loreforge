import type { ApiClient } from "../../api/client";

export type AuthStatus = "initializing" | "authenticated" | "unauthenticated";

export type AuthSession = {
  apiKey: string;
  label: string;
};

export type AuthIdentity = {
  displayName: string;
};

export type LoginCredentials = {
  apiKey: string;
  label: string;
};

export type AuthContextValue = {
  apiClient: ApiClient;
  clearAuthError: () => void;
  credential: AuthSession | null;
  error: string | null;
  identity: AuthIdentity | null;
  login: (credentials: LoginCredentials) => Promise<void>;
  logout: () => void;
  status: AuthStatus;
};
