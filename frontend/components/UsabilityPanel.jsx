import { useEffect, useState } from "react";
import { ClipboardCheck } from "lucide-react";
import Button from "./Button";
import { Teacher as TeacherAPI } from "../lib/api";
import logger from "../lib/logger";
import { useI18n } from "../lib/i18n";

const ITEMS = 10; // шкала SUS: десять утверждений, оценки 1-5 (game/usability.py)
const RATINGS = [1, 2, 3, 4, 5];

const fill = (template, values) =>
  Object.entries(values).reduce(
    (text, [key, value]) => text.replace(`{${key}}`, value),
    template
  );

// Оценка удобства кабинета самим преподавателем по стандартной шкале SUS. Свёрнута, чтобы не мешать работе.
export default function UsabilityPanel() {
  const { t } = useI18n();
  const [answeredAt, setAnsweredAt] = useState(undefined); // undefined: ещё не знаем
  const [open, setOpen] = useState(false);
  const [answers, setAnswers] = useState(() => Array(ITEMS).fill(0));
  const [comment, setComment] = useState("");
  const [state, setState] = useState("idle"); // idle | sending | done | error
  const [showIncomplete, setShowIncomplete] = useState(false);

  useEffect(() => {
    let cancelled = false;
    TeacherAPI.usabilityStatus()
      .then((res) => {
        if (!cancelled) setAnsweredAt(res.answered_at);
      })
      .catch((error) => {
        logger.error("Usability status load failed:", error);
        if (!cancelled) setAnsweredAt(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const complete = answers.every((a) => a >= 1);

  const submit = async (event) => {
    event.preventDefault();
    if (!complete) {
      setShowIncomplete(true);
      return;
    }
    setState("sending");
    try {
      await TeacherAPI.submitUsability(answers, comment.trim());
      setState("done");
      setAnsweredAt(new Date().toISOString());
      setOpen(false);
    } catch (error) {
      logger.error("Usability submit failed:", error);
      setState("error");
    }
  };

  const setAnswer = (index, value) => {
    setAnswers((prev) => prev.map((a, i) => (i === index ? value : a)));
    setShowIncomplete(false);
  };

  if (answeredAt === undefined) return null; // пока неизвестно, оценивал ли преподаватель

  return (
    <section
      aria-labelledby="usability-title"
      className="bg-surface border border-border rounded-3xl p-4 sm:p-6 shadow-sm mt-6"
    >
      <h2 id="usability-title" className="text-lg font-bold text-text mb-1 flex items-center gap-2">
        <ClipboardCheck size={18} className="text-primary" aria-hidden="true" />
        {t("teacher.usability.title")}
      </h2>
      <p className="text-xs text-muted mb-3">{t("teacher.usability.subtitle")}</p>

      {state === "done" ? (
        <p role="status" className="text-sm text-emerald-700 dark:text-emerald-400">
          {t("teacher.usability.thanks")}
        </p>
      ) : answeredAt ? (
        <p className="text-sm text-muted">
          {fill(t("teacher.usability.answered"), {
            date: new Date(answeredAt).toLocaleDateString(),
          })}
        </p>
      ) : null}

      {!open ? (
        <div className="mt-3">
          <Button variant="secondary" size="sm" onClick={() => setOpen(true)} aria-expanded={false}>
            {t("teacher.usability.open")}
          </Button>
        </div>
      ) : (
        <form onSubmit={submit} className="mt-4 space-y-4" noValidate>
          {Array.from({ length: ITEMS }, (_, index) => (
            <fieldset key={index} className="rounded-2xl border border-border bg-panel p-3">
              <legend className="px-1 text-sm text-text">
                {index + 1}. {t(`teacher.usability.q.${index + 1}`)}
              </legend>
              <div className="mt-2 flex items-center justify-between gap-2">
                <span className="hidden sm:block text-xs text-muted w-28">
                  {t("teacher.usability.scaleLow")}
                </span>
                <div className="flex gap-2 mx-auto sm:mx-0">
                  {RATINGS.map((value) => {
                    const checked = answers[index] === value;
                    return (
                      <label
                        key={value}
                        className={`grid h-11 w-11 cursor-pointer place-items-center rounded-xl border text-sm font-semibold transition focus-within:ring-2 focus-within:ring-primary ${
                          checked
                            ? "border-primary bg-primary text-on-primary"
                            : "border-border bg-surface text-text hover:border-primary"
                        }`}
                      >
                        <input
                          type="radio"
                          className="sr-only"
                          name={`sus-${index + 1}`}
                          value={value}
                          checked={checked}
                          onChange={() => setAnswer(index, value)}
                          aria-label={fill(t("teacher.usability.rating"), { n: value })}
                        />
                        {value}
                      </label>
                    );
                  })}
                </div>
                <span className="hidden sm:block text-xs text-muted w-28 text-right">
                  {t("teacher.usability.scaleHigh")}
                </span>
              </div>
              <div className="mt-1 flex justify-between text-xs text-muted sm:hidden">
                <span>{t("teacher.usability.scaleLow")}</span>
                <span>{t("teacher.usability.scaleHigh")}</span>
              </div>
            </fieldset>
          ))}

          <label className="block text-sm text-muted">
            {t("teacher.usability.commentLabel")}
            <textarea
              className="mt-1 w-full rounded-xl border border-border bg-surface px-3 py-2 text-sm text-text focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
              rows={3}
              maxLength={1000}
              value={comment}
              onChange={(e) => setComment(e.target.value)}
            />
          </label>

          {showIncomplete ? (
            <p role="alert" className="text-sm text-error">
              {t("teacher.usability.incomplete")}
            </p>
          ) : null}
          {state === "error" ? (
            <p role="alert" className="text-sm text-error">
              {t("teacher.usability.error")}
            </p>
          ) : null}

          <Button type="submit" disabled={state === "sending"}>
            {state === "sending" ? t("teacher.usability.sending") : t("teacher.usability.submit")}
          </Button>
        </form>
      )}
    </section>
  );
}
