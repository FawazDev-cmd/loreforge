import type { ReactNode } from "react";

import "./ui.css";

type BadgeTone = "neutral" | "success" | "warning" | "error" | "info";

type BadgeProps = {
  children: ReactNode;
  tone?: BadgeTone;
};

export function Badge({ children, tone = "neutral" }: BadgeProps) {
  return <span className={`badge badge--${tone}`}>{children}</span>;
}
