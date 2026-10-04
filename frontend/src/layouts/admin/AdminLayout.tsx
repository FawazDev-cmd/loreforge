import { Link, Outlet } from "react-router-dom";

import { routes } from "../../app/router/routes";
import { NavigationLink } from "../../components/navigation/NavigationLink";
import { AuthControls } from "../../features/auth/AuthControls";

export function AdminLayout() {
  return (
    <div className="app-shell">
      <header className="topbar">
        <Link className="brand" to={routes.admin}>
          <span className="brand__mark" aria-hidden="true">
            L
          </span>
          <span>LoreForge Engineering</span>
        </Link>

        <nav aria-label="Surface navigation" className="nav-row">
          <NavigationLink to={routes.workspace}>Workspace</NavigationLink>
          <NavigationLink to={routes.home}>Product</NavigationLink>
        </nav>

        <AuthControls />

        <details className="mobile-menu">
          <summary className="mobile-menu__button" aria-label="Open navigation">
            <span aria-hidden="true">☰</span>
          </summary>

          <nav aria-label="Mobile navigation" className="mobile-menu__panel">
            <nav aria-label="Engineering navigation" className="mobile-menu__section">
              <NavigationLink end to={routes.admin}>
                Operations
              </NavigationLink>
              <NavigationLink to={routes.adminSystem}>System</NavigationLink>
              <NavigationLink to={routes.adminMetrics}>Metrics</NavigationLink>
              <NavigationLink to={routes.adminEvaluation}>Evaluation</NavigationLink>
            </nav>

            <div className="mobile-menu__divider" />

            <nav aria-label="Surface navigation" className="mobile-menu__section">
              <NavigationLink to={routes.workspace}>Workspace</NavigationLink>
              <NavigationLink to={routes.home}>Product</NavigationLink>
              <AuthControls />
            </nav>
          </nav>
        </details>
      </header>

      <div className="layout-grid">
        <aside className="sidebar">
          <nav aria-label="Engineering navigation" className="nav-stack">
            <NavigationLink end to={routes.admin}>
              Operations
            </NavigationLink>
            <NavigationLink to={routes.adminSystem}>System</NavigationLink>
            <NavigationLink to={routes.adminMetrics}>Metrics</NavigationLink>
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