import { Link, Outlet } from "react-router-dom";

import { NavigationLink } from "../../components/navigation/NavigationLink";
import { AuthControls } from "../../features/auth/AuthControls";
import { routes } from "../../app/router/routes";

export function WorkspaceLayout() {
  return (
    <div className="app-shell">
      <header className="topbar">
        <Link className="brand" to={routes.workspace}>
          <span className="brand__mark" aria-hidden="true">
            L
          </span>
          <span>LoreForge Workspace</span>
        </Link>
        <nav aria-label="Account navigation" className="nav-row">
          <NavigationLink to={routes.home}>Product</NavigationLink>
          <NavigationLink to={routes.admin}>Admin</NavigationLink>
        </nav>
        <AuthControls />
      </header>
      <div className="layout-grid">
        <aside className="sidebar">
          <nav aria-label="Workspace navigation" className="nav-stack">
            <NavigationLink end to={routes.workspace}>
              Overview
            </NavigationLink>
            <NavigationLink to={routes.workspaceDocuments}>Documents</NavigationLink>
            <NavigationLink to={routes.workspaceUpload}>Upload</NavigationLink>
            <NavigationLink to={routes.workspaceChat}>AskMe</NavigationLink>
          </nav>
        </aside>
        <main className="workspace-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
