import type { ReactNode } from "react";

import "../ui/ui.css";

type StatusTone = "success" | "warning" | "error" | "info" | "neutral";

type StatusIndicatorProps = {
  children: ReactNode;
  tone?: StatusTone;
};

export function StatusIndicator({ children, tone = "neutral" }: StatusIndicatorProps) {
  return (
    <span className={`status status--${tone}`}>
      <span className="status__dot" aria-hidden="true" />
      {children}
    </span>
  );
}
