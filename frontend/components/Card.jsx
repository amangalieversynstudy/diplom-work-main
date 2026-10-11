// Тон — лёгкий цветной градиент поверх card-bg.
// Светлая тема даёт мягкие пастельные оверлеи, тёмная — насыщенные.
const toneMap = {
  default: "from-primary/5 via-transparent to-accent/5",
  aurora:  "from-primary/15 via-transparent to-accent/10",
  ember:   "from-accent/20 via-transparent to-accent-dk/15",
  moss:    "from-primary/15 via-transparent to-primary-dk/10",
  night:   "from-primary/10 via-transparent to-accent/5",
};

export default function Card({
  title,
  subtitle,
  children,
  footer,
  tone = "default",
  variant = "default",
  className = "",
}) {
  const gradient = toneMap[tone] || toneMap.default;
  // variant="scroll" — рамка-свиток для экранов ученика; по умолчанию вид прежний (экраны преподавателя).
  const scroll = variant === "scroll";
  return (
    <div
      className={`relative ${scroll ? "scroll-frame text-card-text overflow-hidden" : "rounded-3xl border border-card-border bg-card-bg text-card-text shadow-card overflow-hidden transition hover:border-primary/40"} ${className}`}
    >
      {!scroll && <div className={`absolute inset-0 bg-gradient-to-br ${gradient} pointer-events-none`} aria-hidden />}
      <div className="relative p-6">
        {(title || subtitle) && (
          <div className="mb-4">
            {title && <h3 className={scroll ? "font-title text-2xl tracking-wide text-card-text" : "text-xl font-semibold tracking-wide text-card-text"}>{title}</h3>}
            {subtitle && <p className="text-sm text-card-muted">{subtitle}</p>}
          </div>
        )}
        <div className="min-h-[32px]">{children}</div>
        {footer && (
          <div className="mt-5 pt-4 border-t border-card-border">{footer}</div>
        )}
      </div>
    </div>
  );
}
