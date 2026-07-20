import type { DocumentStatus } from "../../api/contracts";
import { StatusIndicator } from "../../components/feedback/StatusIndicator";

type DocumentStatusBadgeProps = {
  status: DocumentStatus;
};

export function DocumentStatusBadge({ status }: DocumentStatusBadgeProps) {
  return <StatusIndicator tone={statusTone(status)}>{status}</StatusIndicator>;
}

function statusTone(status: DocumentStatus) {
  switch (status) {
    case "READY":
      return "success";
    case "INGESTING":
    case "UPLOADED":
      return "info";
    case "FAILED":
      return "error";
    case "DELETED":
      return "neutral";
  }
}

