import Card from "./Card";

/**
 * Единые пустые экраны и загрузка для экранов ученика: пергаментный свиток
 * с иконкой и фразой (пустое состояние) либо с пульсирующими строками (загрузка).
 */
export default function EmptyScroll({ icon: Icon, children, className = "" }) {
  return (
    <Card variant="scroll" className={className}>
      <div className="py-6 text-center">
        {Icon ? <Icon size={44} className="mx-auto mb-3 text-faint" aria-hidden="true" /> : null}
        <p className="font-title text-xl text-card-text">{children}</p>
      </div>
    </Card>
  );
}

export function SkeletonScroll({ label, rows = 3, className = "" }) {
  return (
    <div role="status" aria-busy="true" className={className}>
      <span className="sr-only">{label}</span>
      <Card variant="scroll">
        <div className="animate-pulse space-y-3" aria-hidden="true">
          {Array.from({ length: rows }).map((_, i) => (
            <div key={i} className="h-10 rounded-xl bg-border" />
          ))}
        </div>
      </Card>
    </div>
  );
}
