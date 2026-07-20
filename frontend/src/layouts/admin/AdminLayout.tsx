import { Link, Outlet } from "react-router-dom";

import { NavigationLink } from "../../components/navigation/NavigationLink";
import { AuthControls } from "../../features/auth/AuthControls";
import { routes } from "../../app/router/routes";

export function AdminLayout() {
  return (
    <div className="app-shell">
      <header className="topbar">
        <Link className="brand" to={routes.admin}>
          <span className="brand__mark" aria-hidden="true">
            L
          </span>
          <span>LoreForge Admin</span>
        </Link>
        <nav aria-label="Surface navigation" className="nav-row">
          <NavigationLink to={routes.workspace}>Workspace</NavigationLink>
          <NavigationLink to={routes.home}>Product</NavigationLink>
        </nav>
        <AuthControls />
      </header>
      <div className="layout-grid">
        <aside className="sidebar">
          <nav aria-label="Admin navigation" className="nav-stack">
            <NavigationLink end to={routes.admin}>
              Overview
            </NavigationLink>
            <NavigationLink to={routes.adminSystem}>System</NavigationLink>
            <NavigationLink to={routes.adminEvaluation}>Evaluation</NavigationLink>
          </nav>
        </aside>
        <main className="admin-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
