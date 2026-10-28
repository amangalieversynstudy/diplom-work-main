/**
 * Пустой экран кабинета и Студии: значок, что здесь будет, подсказка и действие (CTA). Для экранов ученика
 * есть пергаментный EmptyScroll; этот — в спокойном стиле рабочих экранов преподавателя.
 */
export default function EmptyState({ icon: Icon, title, hint, children, className = "" }) {
  return (
    <div
      className={`rounded-3xl border border-dashed border-border bg-surface px-4 py-10 text-center sm:px-6 sm:py-12 ${className}`}
    >
      {Icon ? (
        <div className="mx-auto mb-4 grid h-14 w-14 place-items-center rounded-2xl border border-primary/20 bg-primary/10">
          <Icon size={26} className="text-primary" aria-hidden="true" />
        </div>
      ) : null}
      <h2 className="text-lg font-semibold text-text">{title}</h2>
      {hint ? <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-muted">{hint}</p> : null}
      {/* на телефоне кнопки во всю ширину: длинная подпись не ломается внутри кнопки */}
      {children ? (
        <div className="mt-6 flex flex-col items-stretch justify-center gap-3 sm:flex-row sm:flex-wrap sm:items-center">
          {children}
        </div>
      ) : null}
    </div>
  );
}
