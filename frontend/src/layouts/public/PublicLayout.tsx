import { Link, Outlet } from "react-router-dom";

import { NavigationLink } from "../../components/navigation/NavigationLink";
import { routes } from "../../app/router/routes";

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
          <NavigationLink to={routes.admin}>Admin</NavigationLink>
          <NavigationLink to={routes.login}>Sign in</NavigationLink>
        </nav>
      </header>
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
