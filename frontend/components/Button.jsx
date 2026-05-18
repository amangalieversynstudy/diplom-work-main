export default function Button({ children, variant = "primary", className = "", ...props }) {
  const base =
    "inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-full font-medium tracking-wide transition transform hover:-translate-y-0.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/50 disabled:opacity-50 disabled:cursor-not-allowed";
  const variants = {
    primary: "bg-primary text-white shadow-glow hover:bg-primary-dk",
    secondary: "bg-primary/10 border border-primary/20 text-primary hover:border-primary/40",
    outline: "border border-border text-muted hover:bg-panel hover:text-text",
    ghost: "text-muted hover:text-text hover:bg-panel",
    danger: "bg-gradient-to-r from-error to-orange-500 text-white",
  };
  const styles = variants[variant] || variants.primary;
  return (
    <button className={`${base} ${styles} ${className}`} {...props}>
      {children}
    </button>
  );
}
