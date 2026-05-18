export default function Button({
  children,
  variant = "primary",
  size = "md",
  className = "",
  ...props
}) {
  const base =
    "inline-flex items-center gap-2 font-semibold tracking-wide transition-all duration-200 transform hover:-translate-y-0.5 active:translate-y-0 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/50 disabled:opacity-40 disabled:cursor-not-allowed disabled:transform-none rounded-xl cursor-pointer";

  const sizes = {
    sm: "px-4 py-2 text-[13px]",
    md: "px-5 py-2.5 text-sm",
    lg: "px-7 py-3.5 text-base",
  };

  const variants = {
    primary:
      "bg-primary text-bg hover:bg-jade shadow-[0_4px_24px_rgba(46,204,138,0.35)] hover:shadow-[0_6px_32px_rgba(46,204,138,0.5)]",
    accent:
      "bg-accent text-white hover:bg-ember shadow-[0_4px_24px_rgba(232,105,58,0.3)] hover:shadow-[0_6px_32px_rgba(232,105,58,0.45)]",
    gold:
      "bg-gold text-bg hover:bg-yellow-500 shadow-[0_4px_24px_rgba(212,168,83,0.3)]",
    secondary:
      "bg-primary/10 border border-primary/25 text-primary hover:bg-primary/18 hover:border-primary/40",
    outline:
      "border border-primary/30 text-mist/80 hover:border-primary hover:text-primary hover:bg-primary/5",
    ghost:
      "text-mist/60 hover:text-primary hover:bg-primary/8",
    danger:
      "bg-gradient-to-r from-red-600 to-accent text-white hover:opacity-90",
  };

  return (
    <button
      className={`${base} ${sizes[size] || sizes.md} ${variants[variant] || variants.primary} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
