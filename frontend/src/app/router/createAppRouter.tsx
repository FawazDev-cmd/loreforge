import { createBrowserRouter, type RouteObject } from "react-router-dom";

import { ProtectedRoute } from "../../features/auth/ProtectedRoute";
import { AdminLayout } from "../../layouts/admin/AdminLayout";
import { PublicLayout } from "../../layouts/public/PublicLayout";
import { WorkspaceLayout } from "../../layouts/workspace/WorkspaceLayout";
import { AdminEvaluationPage } from "../../pages/admin/AdminEvaluationPage";
import { AdminOverviewPage } from "../../pages/admin/AdminOverviewPage";
import { AdminSystemPage } from "../../pages/admin/AdminSystemPage";
import { LoginPage } from "../../pages/public/LoginPage";
import { NotFoundPage } from "../../pages/public/NotFoundPage";
import { PublicHomePage } from "../../pages/public/PublicHomePage";
import { WorkspaceChatPage } from "../../pages/workspace/WorkspaceChatPage";
import { WorkspaceDocumentsPage } from "../../pages/workspace/WorkspaceDocumentsPage";
import { WorkspaceHomePage } from "../../pages/workspace/WorkspaceHomePage";
import { WorkspaceUploadPage } from "../../pages/workspace/WorkspaceUploadPage";
import { routes } from "./routes";

export const appRoutes: RouteObject[] = [
  {
    element: <PublicLayout />,
    children: [
      { path: routes.home, element: <PublicHomePage /> },
      { path: routes.login, element: <LoginPage /> },
    ],
  },
  {
    path: routes.workspace,
    element: (
      <ProtectedRoute>
        <WorkspaceLayout />
      </ProtectedRoute>
    ),
    children: [
      { index: true, element: <WorkspaceHomePage /> },
      { path: "documents", element: <WorkspaceDocumentsPage /> },
      { path: "documents/upload", element: <WorkspaceUploadPage /> },
      { path: "chat", element: <WorkspaceChatPage /> },
    ],
  },
  {
    path: routes.admin,
    element: (
      // Backend auth currently exposes ownership only, not an admin/RBAC claim.
      <ProtectedRoute>
        <AdminLayout />
      </ProtectedRoute>
    ),
    children: [
      { index: true, element: <AdminOverviewPage /> },
      { path: "system", element: <AdminSystemPage /> },
      { path: "evaluation", element: <AdminEvaluationPage /> },
    ],
  },
  { path: "*", element: <NotFoundPage /> },
];

export function createAppRouter() {
  return createBrowserRouter(appRoutes);
}
