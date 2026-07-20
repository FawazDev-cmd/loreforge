import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { routes } from "../../app/router/routes";
import { ErrorState } from "../../components/feedback/ErrorState";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Input } from "../../components/ui/Input";
import { PageHeader } from "../../components/ui/PageHeader";
import { useAuth } from "../../features/auth/useAuth";
import { loginSchema, type LoginFormValues } from "../../schemas/auth";

type RouteState = {
  from?: {
    pathname?: string;
  };
};

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { error, login } = useAuth();
  const [submissionError, setSubmissionError] = useState<string | null>(null);
  const {
    formState: { errors, isSubmitting, isValid },
    handleSubmit,
    register,
  } = useForm<LoginFormValues>({
    mode: "onChange",
    resolver: zodResolver(loginSchema),
  });

  const routeState = location.state as RouteState | null;
  const redirectTo = routeState?.from?.pathname ?? routes.workspace;

  async function onSubmit(values: LoginFormValues) {
    setSubmissionError(null);
    try {
      await login(values);
      navigate(redirectTo, { replace: true });
    } catch {
      setSubmissionError("Sign in failed. Check the API key and try again.");
    }
  }

  return (
    <section className="stack">
      <PageHeader
        title="Sign in"
        description="Enter a LoreForge bearer API key. The frontend verifies it against the existing backend contract before opening protected routes."
        actions={
          <Button as={Link} to={routes.home} variant="secondary">
            Product
          </Button>
        }
      />
      <Card>
        <form aria-describedby="login-status" className="form-grid" onSubmit={handleSubmit(onSubmit)}>
          <Input
            autoComplete="username"
            error={errors.label?.message}
            label="Workspace label"
            {...register("label")}
          />
          <Input
            autoComplete="current-password"
            error={errors.apiKey?.message}
            helpText="Use the backend-issued bearer token when authentication is configured."
            label="API key"
            type="password"
            {...register("apiKey")}
          />
          <Button disabled={!isValid || isSubmitting} type="submit">
            {isSubmitting ? "Checking" : "Continue"}
          </Button>
        </form>
      </Card>
      {submissionError || error ? (
        <ErrorState message={submissionError ?? error ?? "Authentication failed."} title="Authentication failed" />
      ) : null}
    </section>
  );
}
