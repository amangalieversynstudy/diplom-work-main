export default function Button({ children, variant = "primary", className = "", ...props }) {
  const base =
    "inline-flex items-center gap-2 px-5 py-2.5 rounded-full font-medium tracking-wide transition transform hover:-translate-y-0.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 disabled:opacity-50 disabled:cursor-not-allowed";
  const variants = {
    primary: "bg-gradient-to-r from-primary via-aurora to-accent text-white shadow-glow",
    secondary: "bg-white/10 border border-white/20 text-white hover:border-accent/50",
    outline: "border border-white/30 text-white hover:bg-white/10",
    ghost: "text-white/80 hover:text-white hover:bg-white/5",
    danger: "bg-gradient-to-r from-rose-500 to-orange-500 text-white",
  };
  const styles = variants[variant] || variants.primary;
  return (
    <button className={`${base} ${styles} ${className}`} {...props}>
      {children}
    </button>
  );
}
