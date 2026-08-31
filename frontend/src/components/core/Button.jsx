import "./Button.css";

/**
 * The one button component every page should use instead of hand-rolling
 * `.ec-signin-btn`/`.ec-logout-btn`-style one-offs (see SignInScreen.jsx,
 * the old DashboardPage) — accounts/pies pages are the first callers.
 *
 * @param {{
 *   variant?: "primary" | "secondary" | "danger" | "ghost",
 *   size?: "md" | "sm",
 *   isLoading?: boolean,
 *   type?: "button" | "submit",
 * } & React.ButtonHTMLAttributes<HTMLButtonElement>} props
 */
function Button({
  variant = "secondary",
  size = "md",
  isLoading = false,
  type = "button",
  disabled,
  className,
  children,
  ...rest
}) {
  const classes = ["ec-btn", `ec-btn-${variant}`, `ec-btn-${size}`, className]
    .filter(Boolean)
    .join(" ");

  return (
    <button type={type} className={classes} disabled={disabled || isLoading} {...rest}>
      {isLoading ? "…" : children}
    </button>
  );
}

export default Button;
