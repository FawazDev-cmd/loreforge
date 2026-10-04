import { Link, Outlet } from "react-router-dom";

import { routes } from "../../app/router/routes";
import { NavigationLink } from "../../components/navigation/NavigationLink";

export function PublicLayout() {
  return (
    <div className="app-shell">
      <header className="topbar">
        <Link className="brand" to={routes.home}>
          <span className="brand__mark" aria-hidden="true">
            L
          </span>
          <span>LoreForge</span>
        </Link>

        <nav aria-label="Public navigation" className="nav-row">
          <NavigationLink to={routes.workspace}>Workspace</NavigationLink>
          <NavigationLink to={routes.admin}>Engineering</NavigationLink>
          <NavigationLink to={routes.login}>Sign in</NavigationLink>
        </nav>

        <details className="mobile-menu">
          <summary className="mobile-menu__button" aria-label="Open navigation">
            <span aria-hidden="true">☰</span>
          </summary>

          <nav aria-label="Mobile navigation" className="mobile-menu__panel">
            <NavigationLink to={routes.workspace}>Workspace</NavigationLink>
            <NavigationLink to={routes.admin}>Engineering</NavigationLink>
            <NavigationLink to={routes.login}>Sign in</NavigationLink>
          </nav>
        </details>
      </header>

      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}