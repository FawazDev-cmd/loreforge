import { useNavigate } from "react-router-dom";

import { Button } from "../../components/ui/Button";
import { routes } from "../../app/router/routes";
import { useAuth } from "./useAuth";

export function AuthControls() {
  const navigate = useNavigate();
  const { identity, logout } = useAuth();

  function handleLogout() {
    logout();
    navigate(routes.login, { replace: true });
  }

  return (
    <div className="auth-controls">
      {identity ? <span className="auth-controls__identity">{identity.displayName}</span> : null}
      <Button onClick={handleLogout} type="button" variant="ghost">
        Log out
      </Button>
    </div>
  );
}
