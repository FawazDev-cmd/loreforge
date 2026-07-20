import { Link } from "react-router-dom";

import { routes } from "../../app/router/routes";
import { Button } from "../../components/ui/Button";
import { ErrorState } from "../../components/feedback/ErrorState";

export function NotFoundPage() {
  return (
    <main className="main-content">
      <ErrorState
        title="Page not found"
        message="The route does not exist in the LoreForge product shell."
        action={
          <Button as={Link} to={routes.home}>
            Return home
          </Button>
        }
      />
    </main>
  );
}
