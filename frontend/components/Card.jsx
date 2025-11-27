const toneMap = {
  default: "from-white/15 via-white/0 to-white/5",
  aurora: "from-primary/30 via-transparent to-accent/20",
  ember: "from-orange-500/20 via-transparent to-red-900/20",
  moss: "from-emerald-500/25 via-transparent to-slate-900/40",
  night: "from-[#1b1f3a]/80 via-[#0d1327]/90 to-[#05060f]/95",
};

export default function Card({
  title,
  subtitle,
  children,
  footer,
  tone = "default",
  className = "",
}) {
  const gradient = toneMap[tone] || toneMap.default;
  return (
    <div
      className={`relative rounded-3xl border border-white/10 bg-[#080c1c]/80 shadow-card overflow-hidden transition hover:border-white/20 ${className}`}
    >
      <div className={`absolute inset-0 bg-gradient-to-br ${gradient} opacity-80`} aria-hidden />
      <div className="absolute inset-0" aria-hidden>
        <div className="absolute inset-0 mix-blend-screen opacity-20" style={{ backgroundImage: "radial-gradient(circle at 15% 20%, rgba(255,255,255,0.4), transparent 45%)" }} />
      </div>
      <div className="relative p-6">
        {(title || subtitle) && (
          <div className="mb-4">
            {title && <h3 className="text-xl font-semibold tracking-wide">{title}</h3>}
            {subtitle && <p className="text-sm text-white/70">{subtitle}</p>}
          </div>
        )}
        <div className="min-h-[32px]">{children}</div>
        {footer && (
          <div className="mt-5 pt-4 border-t border-white/10">{footer}</div>
        )}
      </div>
    </div>
  );
}
