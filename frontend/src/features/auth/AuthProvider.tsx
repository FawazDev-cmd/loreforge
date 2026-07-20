import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { ApiClientError, UnauthorizedApiError, createApiClient } from "../../api/client";
import type { DocumentListResponse } from "../../api/contracts";
import { frontendConfig } from "../../app/config/env";
import { readStoredAuthSession, removeStoredAuthSession, writeStoredAuthSession } from "./storage";
import { AuthContext } from "./AuthContext";
import type { AuthContextValue, AuthIdentity, AuthSession, AuthStatus, LoginCredentials } from "./types";


type AuthProviderProps = {
  children: React.ReactNode;
  fetchImpl?: typeof fetch;
};

export function AuthProvider({ children, fetchImpl }: AuthProviderProps) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<AuthStatus>("initializing");
  const [session, setSession] = useState<AuthSession | null>(null);
  const [error, setError] = useState<string | null>(null);
  const sessionRef = useRef<AuthSession | null>(null);

  const clearSession = useCallback(
    (message?: string) => {
      sessionRef.current = null;
      setSession(null);
      setStatus("unauthenticated");
      removeStoredAuthSession();
      queryClient.clear();
      setError(message ?? null);
    },
    [queryClient],
  );

  useEffect(() => {
    const storedSession = readStoredAuthSession();
    sessionRef.current = storedSession;
    setSession(storedSession);
    setStatus(storedSession ? "authenticated" : "unauthenticated");
  }, []);

  const apiClient = useMemo(
    () =>
      createApiClient({
        baseUrl: frontendConfig.apiBaseUrl,
        fetchImpl,
        getAuthToken: () => sessionRef.current?.apiKey,
        onUnauthorized: () => clearSession("Your session is no longer authorized."),
      }),
    [clearSession, fetchImpl],
  );

  const login = useCallback(
    async (credentials: LoginCredentials) => {
      const candidateSession = {
        apiKey: credentials.apiKey,
        label: credentials.label.trim(),
      };
      const verificationClient = createApiClient({
        baseUrl: frontendConfig.apiBaseUrl,
        fetchImpl,
        getAuthToken: () => candidateSession.apiKey,
      });

      setError(null);

      try {
        await verificationClient.request<DocumentListResponse>("/admin/documents");
      } catch (caughtError) {
        removeStoredAuthSession();
        if (caughtError instanceof UnauthorizedApiError) {
          setError("The API key was not accepted.");
          throw caughtError;
        }
        if (caughtError instanceof ApiClientError) {
          setError("LoreForge could not verify the API key right now.");
          throw caughtError;
        }
        setError("LoreForge could not be reached.");
        throw caughtError;
      }

      sessionRef.current = candidateSession;
      setSession(candidateSession);
      setStatus("authenticated");
      writeStoredAuthSession(candidateSession);
      await queryClient.invalidateQueries();
    },
    [fetchImpl, queryClient],
  );

  const logout = useCallback(() => {
    clearSession();
  }, [clearSession]);

  const identity = useMemo<AuthIdentity | null>(
    () => (session ? { displayName: session.label } : null),
    [session],
  );

  const value = useMemo<AuthContextValue>(
    () => ({
      apiClient,
      clearAuthError: () => setError(null),
      credential: session,
      error,
      identity,
      login,
      logout,
      status,
    }),
    [apiClient, error, identity, login, logout, session, status],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}