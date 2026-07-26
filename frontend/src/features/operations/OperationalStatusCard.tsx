import type { ReactNode } from "react";

import { StatusIndicator } from "../../components/feedback/StatusIndicator";
import { Card } from "../../components/ui/Card";

export type OperationalStatus = "healthy" | "warning" | "unavailable" | "unknown";

type OperationalStatusCardProps = {
  children?: ReactNode;
  detail: string;
  status: OperationalStatus;
  title: string;
};

const statusLabel: Record<OperationalStatus, string> = {
  healthy: "Healthy",
  warning: "Warning",
  unavailable: "Unavailable",
  unknown: "Unknown",
};

const statusTone: Record<OperationalStatus, "success" | "warning" | "error" | "neutral"> = {
  healthy: "success",
  warning: "warning",
  unavailable: "error",
  unknown: "neutral",
};

export function OperationalStatusCard({ children, detail, status, title }: OperationalStatusCardProps) {
  return (
    <Card className="operation-card">
      <header className="operation-card__header">
        <h2>{title}</h2>
        <StatusIndicator tone={statusTone[status]}>{statusLabel[status]}</StatusIndicator>
      </header>
      <p className="muted">{detail}</p>
      {children ? <div>{children}</div> : null}
    </Card>
  );
}