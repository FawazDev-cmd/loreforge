import type { ReactNode } from "react";

import "../ui/ui.css";

type EmptyStateProps = {
  title: string;
  message: string;
  action?: ReactNode;
};

export function EmptyState({ action, message, title }: EmptyStateProps) {
  return (
    <div className="state state--empty">
      <h2>{title}</h2>
      <p>{message}</p>
      {action ? <div>{action}</div> : null}
    </div>
  );
}
