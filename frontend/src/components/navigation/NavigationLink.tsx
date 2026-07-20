import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";

import "./navigation.css";

type NavigationLinkProps = {
  children: ReactNode;
  end?: boolean;
  to: string;
};

export function NavigationLink({ children, end = false, to }: NavigationLinkProps) {
  return (
    <NavLink
      className={({ isActive }) =>
        isActive ? "navigation-link navigation-link--active" : "navigation-link"
      }
      end={end}
      to={to}
    >
      {children}
    </NavLink>
  );
}
