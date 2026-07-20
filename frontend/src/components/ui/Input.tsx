import type { InputHTMLAttributes } from "react";

import "./ui.css";

type InputProps = InputHTMLAttributes<HTMLInputElement> & {
  error?: string;
  helpText?: string;
  label: string;
};

export function Input({ error, helpText, id, label, ...props }: InputProps) {
  const inputId = id ?? props.name ?? label.toLowerCase().replaceAll(" ", "-");
  const helpId = helpText ? `${inputId}-help` : undefined;
  const errorId = error ? `${inputId}-error` : undefined;
  const describedBy = [helpId, errorId].filter(Boolean).join(" ") || undefined;

  return (
    <div className="field">
      <label className="field__label" htmlFor={inputId}>
        {label}
      </label>
      <input
        aria-describedby={describedBy}
        aria-invalid={error ? "true" : undefined}
        className="input"
        id={inputId}
        {...props}
      />
      {helpText ? (
        <span className="field__help" id={helpId}>
          {helpText}
        </span>
      ) : null}
      {error ? (
        <span className="field__error" id={errorId}>
          {error}
        </span>
      ) : null}
    </div>
  );
}
