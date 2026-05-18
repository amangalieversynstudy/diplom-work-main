const toneMap = {
  default: {
    bg: "from-surface/80 via-panel/60 to-bg/80",
    glow: "rgba(46,204,138,0.04)",
    border: "border-primary/10",
  },
  jade: {
    bg: "from-primary/15 via-jade/5 to-bg/80",
    glow: "rgba(46,204,138,0.12)",
    border: "border-primary/25",
  },
  ember: {
    bg: "from-accent/15 via-ember/5 to-bg/80",
    glow: "rgba(232,105,58,0.1)",
    border: "border-accent/20",
  },
  gold: {
    bg: "from-gold/15 via-yellow-900/10 to-bg/80",
    glow: "rgba(212,168,83,0.1)",
    border: "border-gold/20",
  },
  forest: {
    bg: "from-emerald-900/40 via-surface/60 to-bg/80",
    glow: "rgba(46,204,138,0.06)",
    border: "border-emerald-800/30",
  },
  night: {
    bg: "from-surface/95 via-panel/90 to-bg/95",
    glow: "rgba(0,0,0,0.3)",
    border: "border-mist/5",
  },
  // Keep legacy tone names for backwards compat
  aurora: {
    bg: "from-primary/15 via-jade/5 to-bg/80",
    glow: "rgba(46,204,138,0.12)",
    border: "border-primary/25",
  },
  moss: {
    bg: "from-emerald-900/40 via-surface/60 to-bg/80",
    glow: "rgba(46,204,138,0.06)",
    border: "border-emerald-800/30",
  },
};

export default function Card({
  title,
  subtitle,
  children,
  footer,
  tone = "default",
  className = "",
  glowing = false,
}) {
  const t = toneMap[tone] || toneMap.default;

  return (
    <div
      className={`
        relative rounded-2xl border ${t.border}
        bg-gradient-to-br ${t.bg}
        backdrop-blur-md overflow-hidden
        transition-all duration-300
        hover:border-primary/20 hover:-translate-y-0.5
        ${glowing ? "jade-glow" : "shadow-card"}
        ${className}
      `}
    >
      {/* Inner glow overlay */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: `radial-gradient(ellipse at 15% 20%, ${t.glow} 0%, transparent 55%)`,
        }}
        aria-hidden
      />

      {/* Top highlight line */}
      <div
        className="absolute top-0 left-8 right-8 h-px"
        style={{ background: "linear-gradient(90deg, transparent, rgba(46,204,138,0.2), transparent)" }}
        aria-hidden
      />

      <div className="relative p-6">
        {(title || subtitle) && (
          <div className="mb-4">
            {title && (
              <h3 className="font-display text-lg font-semibold tracking-wide text-mist">
                {title}
              </h3>
            )}
            {subtitle && (
              <p className="text-sm text-mist/55 mt-0.5">{subtitle}</p>
            )}
          </div>
        )}
        <div className="min-h-[32px]">{children}</div>
        {footer && (
          <div className="mt-5 pt-4 border-t border-primary/10">{footer}</div>
        )}
      </div>
    </div>
  );
}
