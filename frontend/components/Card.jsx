export default function Card({ title, subtitle, children, footer }) {
  return (
    <div className="rounded-xl border border-white/10 bg-surface/60 p-4 shadow-lg shadow-black/20 transition hover:border-white/20 hover:bg-surface/70">
      {(title || subtitle) && (
        <div className="mb-3">
          {title && <h3 className="text-lg font-semibold">{title}</h3>}
          {subtitle && <p className="text-sm text-white/70">{subtitle}</p>}
        </div>
      )}
      <div>{children}</div>
      {footer && (
        <div className="mt-4 pt-3 border-t border-white/10">{footer}</div>
      )}
    </div>
  );
}
