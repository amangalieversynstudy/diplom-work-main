export default function Button({ children, variant = "primary", ...props }) {
  const base =
    "inline-flex items-center gap-2 px-4 py-2 rounded-md font-medium transition transform hover:-translate-y-0.5 hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-accent/40";
  const variants = {
    primary: "bg-primary text-white hover:opacity-95",
    outline: "border border-white/20 hover:border-accent text-white",
    ghost: "hover:bg-white/10",
  };
  return (
    <button className={`${base} ${variants[variant]}`} {...props}>
      {children}
    </button>
  );
}
