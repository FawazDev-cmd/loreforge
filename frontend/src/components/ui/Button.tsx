import type { ButtonHTMLAttributes, ComponentProps, ReactNode } from "react";
import { Link } from "react-router-dom";

import "./ui.css";

type ButtonVariant = "primary" | "secondary" | "ghost";

type BaseButtonProps = {
  children: ReactNode;
  className?: string;
  variant?: ButtonVariant;
};

type NativeButtonProps = ButtonHTMLAttributes<HTMLButtonElement> &
  BaseButtonProps & {
    as?: "button";
  };

type LinkButtonProps = ComponentProps<typeof Link> &
  BaseButtonProps & {
    as: typeof Link;
  };

type ButtonProps = NativeButtonProps | LinkButtonProps;

export function Button(props: ButtonProps) {
  const { children, className = "", variant = "primary" } = props;
  const buttonClassName = `button button--${variant} ${className}`.trim();

  if (props.as === Link) {
    const linkButtonProps = props as LinkButtonProps;
    const {
      as: _as,
      children: _children,
      className: _className,
      variant: _variant,
      ...linkProps
    } = linkButtonProps;
    return (
      <Link className={buttonClassName} {...linkProps}>
        {children}
      </Link>
    );
  }

  const nativeButtonProps = props as NativeButtonProps;
  const {
    as: _as,
    children: _children,
    className: _className,
    variant: _variant,
    ...buttonProps
  } = nativeButtonProps;
  return (
    <button className={buttonClassName} {...buttonProps}>
      {children}
    </button>
  );
}
