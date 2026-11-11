import { useId, useRef, useState } from "react";
import { HelpCircle, X } from "lucide-react";
import { useI18n } from "../lib/i18n";
import { useDialog } from "../lib/useDialog";

const TERMS = [1, 2, 3, 4, 5, 6, 7, 8, 9];

/** Кнопка «?» в шапке и окно со словарём терминов на одну страницу. */
export default function HelpGlossary() {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const dialogRef = useRef(null);
  const titleId = useId();
  useDialog(open, dialogRef, () => setOpen(false));

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label={t("glossary.open")}
        title={t("glossary.open")}
        data-testid="glossary-open"
        className="grid h-10 w-10 place-items-center rounded-full border border-border bg-surface text-muted transition-colors hover:text-text focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
      >
        <HelpCircle size={18} aria-hidden="true" />
      </button>
      {open && (
        <div
          role="presentation"
          className="fixed inset-0 z-[1000] flex items-center justify-center bg-modal-overlay px-4 backdrop-blur-sm"
          onClick={(e) => {
            if (e.target === e.currentTarget) setOpen(false);
          }}
        >
          <div
            ref={dialogRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            className="relative max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-3xl border-2 border-card-border bg-modal-bg p-6 text-modal-text shadow-xl"
          >
            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label={t("glossary.close")}
              className="absolute right-4 top-4 text-card-muted transition-colors hover:text-modal-text"
            >
              <X size={18} />
            </button>
            <h2 id={titleId} className="mb-1 pr-8 font-display text-xl font-bold">
              {t("glossary.title")}
            </h2>
            <p className="mb-4 text-sm text-card-muted">{t("glossary.intro")}</p>
            <dl className="space-y-3">
              {TERMS.map((n) => (
                <div key={n}>
                  <dt className="text-sm font-bold">{t(`glossary.terms.${n}.name`)}</dt>
                  <dd className="text-sm leading-snug text-card-muted">{t(`glossary.terms.${n}.text`)}</dd>
                </div>
              ))}
            </dl>
          </div>
        </div>
      )}
    </>
  );
}
