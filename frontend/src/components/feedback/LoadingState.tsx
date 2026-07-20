import "../ui/ui.css";

type LoadingStateProps = {
  label?: string;
  message?: string;
};

export function LoadingState({ label, message }: LoadingStateProps) {
  const text = label ?? message ?? "Loading";
  return (
    <div aria-live="polite" className="state state--loading">
      <span className="loading-dot" aria-hidden="true" />
      <span>{text}</span>
    </div>
  );
}
