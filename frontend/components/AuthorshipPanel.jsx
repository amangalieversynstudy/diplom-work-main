import { ClipboardPaste, Clock, Copy, Eye, GraduationCap, ShieldCheck } from "lucide-react";
import { useI18n } from "../lib/i18n";

const dur = (sec, t) => {
  const s = Math.max(0, Math.round(Number(sec) || 0));
  const m = Math.floor(s / 60);
  return m > 0 ? `${m} ${t(`${T}.timing.min`)} ${s % 60} ${t(`${T}.timing.sec`)}` : `${s} ${t(`${T}.timing.sec`)}`;
};

const fmt = (template, values = {}) =>
  Object.entries(values).reduce((text, [key, value]) => text.replace(`{${key}}`, value), template);

// Оттенки 700–800 в светлой теме и 400 в тёмной: 400 на светлом фоне не читается.
const ASSISTANCE_STYLE = {
  independent: "border-emerald-400/30 bg-emerald-400/10 text-emerald-700 dark:text-emerald-400",
  hint: "border-primary/30 bg-primary/10 text-primary",
  skeleton: "border-primary/30 bg-primary/10 text-primary",
  mentor: "border-accent/40 bg-accent/15 text-accent-dk",
};

const SIGNAL_ICON = {
  no_editor_data: Eye,
  untaught_construct: GraduationCap,
  same_as_others: Copy,
  explain_missed: GraduationCap,
  fast_solve: Clock,
  away_then_paste: Clock,
};

const T = "teacherStudent.authorship";

// 130 -> «2 мин 10 с»
function Timing({ timing, t }) {
  if (!timing) return null;
  const parts = [];
  if (timing.active_s) parts.push(fmt(t(`${T}.timing.active`), { t: dur(timing.active_s, t) }));
  const head = timing.elapsed_s ? `${t(`${T}.timing.label`)}: ${dur(timing.elapsed_s, t)}` : "";
  const line = [
    head && (parts.length ? `${head}, ${parts.join(", ")}` : head),
    timing.pause_count ? fmt(t(`${T}.timing.pauses`), { n: timing.pause_count }) : "",
    timing.away_count ? fmt(t(`${T}.timing.away`), { n: timing.away_count, t: dur(timing.away_s || 0, t) }) : "",
  ].filter(Boolean);
  if (line.length === 0) return null;
  return <p className="mt-2 text-xs text-muted">{line.join(" · ")}</p>;
}

function Tile({ label, value }) {
  return (
    <div className="rounded-2xl border border-border bg-panel p-4">
      <p className="text-xs font-bold uppercase tracking-widest text-muted">{label}</p>
      <p className="mt-1 font-display text-3xl font-bold text-text">{value}</p>
    </div>
  );
}

/**
 * Кто решил кодовые шаги ученика: сам, с помощью платформы или с признаками внешней помощи.
 * Помощь платформы записана точно; признаки по данным редактора только подсказка для разговора.
 */
export default function AuthorshipPanel({ data }) {
  const { t } = useI18n();
  if (!data) return null;
  const { summary, steps } = data;

  return (
    <section aria-labelledby="authorship-title" className="mx-auto max-w-5xl px-1 pb-16 pt-6">
      <div className="rounded-3xl border border-border bg-surface p-6 md:p-8">
        <div className="flex items-start gap-3">
          <ShieldCheck size={22} className="mt-1 shrink-0 text-primary" aria-hidden="true" />
          <div>
            <h2 id="authorship-title" className="font-display text-2xl font-bold text-text">
              {t(`${T}.title`)}
            </h2>
            <p className="mt-1 max-w-3xl text-sm leading-relaxed text-muted">{t(`${T}.note`)}</p>
          </div>
        </div>

        {steps.length === 0 ? (
          <p className="mt-6 text-muted">{t(`${T}.empty`)}</p>
        ) : (
          <>
            <div className="mt-6 grid grid-cols-2 gap-3 md:grid-cols-4">
              <Tile label={t(`${T}.tiles.solved`)} value={summary.solved} />
              <Tile label={t(`${T}.tiles.independent`)} value={summary.independent} />
              <Tile label={t(`${T}.tiles.assisted`)} value={summary.assisted} />
              <Tile label={t(`${T}.tiles.flagged`)} value={summary.flagged} />
            </div>

            <ul className="mt-6 space-y-3">
              {steps.map((step) => {
                const flagged = step.signals.some((s) => s.code !== "no_editor_data");
                return (
                  <li
                    key={step.task_id}
                    className={`rounded-2xl border p-4 ${
                      flagged ? "border-amber-400/40 bg-amber-400/5" : "border-border bg-panel"
                    }`}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="font-semibold text-text">{step.title}</p>
                        <p className="text-xs text-muted">
                          {step.mission} · {fmt(t(`${T}.attempts`), { n: step.attempts })}
                          {step.paste_share > 0 ? ` · ${fmt(t(`${T}.pasteShare`), { n: step.paste_share })}` : ""}
                        </p>
                      </div>
                      <span
                        className={`shrink-0 rounded-full border px-2.5 py-1 text-xs font-semibold ${ASSISTANCE_STYLE[step.assistance]}`}
                      >
                        {t(`${T}.assistance.${step.assistance}`)}
                      </span>
                    </div>
                    {step.assistance !== "independent" && (
                      <p className="mt-2 text-xs text-muted">
                        {fmt(t(`${T}.helpUses`), step.help_uses)}
                      </p>
                    )}
                    <Timing timing={step.timing} t={t} />
                    {step.explain && (
                      <p className="mt-2 text-xs text-muted">
                        {t(`${T}.explain.title`)}: {fmt(t(`${T}.explain.${step.explain.status}`), step.explain)}
                      </p>
                    )}
                    {step.signals.length > 0 && (
                      <ul className="mt-3 space-y-1.5">
                        {step.signals.map((signal) => (
                          <li key={signal.code} className="flex items-start gap-2 text-sm text-text">
                            {(() => {
                              const Icon = SIGNAL_ICON[signal.code] || ClipboardPaste;
                              return (
                                <Icon
                                  size={15}
                                  className={`mt-0.5 shrink-0 ${
                                    signal.code === "no_editor_data" ? "text-muted" : "text-amber-700 dark:text-amber-400"
                                  }`}
                                  aria-hidden="true"
                                />
                              );
                            })()}
                            <span>{fmt(t(`${T}.signals.${signal.code}`), signal)}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </li>
                );
              })}
            </ul>
          </>
        )}
      </div>
    </section>
  );
}
