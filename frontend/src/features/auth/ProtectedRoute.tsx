import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { LoadingState } from "../../components/feedback/LoadingState";
import { routes } from "../../app/router/routes";
import { useAuth } from "./useAuth";

type ProtectedRouteProps = {
  children: ReactNode;
};

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const location = useLocation();
  const { status } = useAuth();

  if (status === "initializing") {
    return <LoadingState label="Restoring authentication." />;
  }

  if (status === "unauthenticated") {
    return <Navigate replace state={{ from: location }} to={routes.login} />;
  }

  return children;
}
