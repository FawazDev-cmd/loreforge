import type { ReactNode } from "react";

import "../ui/ui.css";

type ErrorStateProps = {
  action?: ReactNode;
  message: string;
  title?: string;
};

export function ErrorState({ action, message, title = "Something needs attention" }: ErrorStateProps) {
  return (
    <div className="state state--error" role="alert">
      <h2>{title}</h2>
      <p>{message}</p>
      {action ? <div>{action}</div> : null}
    </div>
  );
}
