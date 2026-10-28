import { Loader2 } from "lucide-react";

const SIZES = {
  sm: "px-4 py-1.5 text-sm",
  md: "px-5 py-2.5",
  lg: "px-7 py-3.5 text-lg",
};

// loading: кнопка занята запросом — крутится значок, повторное нажатие невозможно (защита от двойной отправки).
export default function Button({
  children,
  variant = "primary",
  size = "md",
  icon: Icon,
  loading = false,
  disabled,
  className = "",
  ...props
}) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded-full font-medium tracking-wide transition transform hover:-translate-y-0.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0";
  const variants = {
    primary: "bg-primary text-on-primary shadow-glow hover:bg-primary-dk",
    secondary: "bg-primary/10 border border-primary/20 text-primary hover:border-primary/40",
    outline: "border border-border text-muted hover:bg-panel hover:text-text",
    ghost: "text-muted hover:text-text hover:bg-panel",
    // «печать»: кнопка-руна для экранов ученика
    rune: "scroll-btn",
    danger: "bg-error text-white dark:text-bg hover:brightness-110",
  };
  const styles = variants[variant] || variants.primary;
  return (
    <button
      className={`${base} ${SIZES[size] || SIZES.md} ${styles} ${className}`}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {loading ? (
        <Loader2 size={16} className="animate-spin" aria-hidden="true" />
      ) : Icon ? (
        <Icon size={16} aria-hidden="true" />
      ) : null}
      {children}
    </button>
  );
}
