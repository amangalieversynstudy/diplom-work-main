import { Wand2 } from "lucide-react";
import { localized } from "../lib/studioTemplates";

/**
 * «Быстрый старт по шаблону»: карточки готовых пресетов над формой Студии. Клик заполняет поля формы
 * (заполнение делает onPick), преподавателю остаётся поправить текст и сохранить.
 */
export default function TemplatePicker({ templates, onPick, picked, t, language, compact = false }) {
  return (
    <div className="mb-4 rounded-2xl border border-primary/20 bg-primary/5 p-3 sm:p-4">
      <p className="mb-1 flex items-center gap-2 text-sm font-semibold text-text">
        <Wand2 size={16} className="text-primary" aria-hidden="true" />
        {t("pilot.templates.title")}
      </p>
      <p className="mb-3 text-xs text-muted">{t("pilot.templates.hint")}</p>
      <div className={`grid gap-2 ${compact ? "sm:grid-cols-3" : "sm:grid-cols-2 lg:grid-cols-4"}`}>
        {templates.map((template) => {
          const active = picked === template.id;
          return (
            <button
              key={template.id}
              type="button"
              aria-pressed={active}
              onClick={() => onPick(template)}
              className={`flex min-h-[44px] flex-col items-start gap-0.5 rounded-xl border px-3 py-2 text-left transition-colors ${
                active
                  ? "border-primary bg-primary/10"
                  : "border-border bg-surface hover:border-primary/50 hover:bg-panel"
              }`}
            >
              <span className="text-sm font-semibold text-text">{localized(template.label, language)}</span>
              <span className="text-xs leading-snug text-muted">{localized(template.hint, language)}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
