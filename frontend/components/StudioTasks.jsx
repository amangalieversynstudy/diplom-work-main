import { useCallback, useEffect, useState } from "react";
import {
  ArrowDown,
  ArrowUp,
  BookOpen,
  Check,
  Code2,
  HelpCircle,
  Pencil,
  Plus,
  Trash2,
  X,
} from "lucide-react";
import Button from "./Button";
import { Studio as StudioAPI } from "../lib/api";
import logger from "../lib/logger";

const TYPES = ["story", "quiz", "code"];
const ICONS = { story: BookOpen, quiz: HelpCircle, code: Code2 };

const inputCls =
  "w-full rounded-xl border border-border bg-panel px-3.5 py-2.5 text-sm text-text placeholder:text-faint focus:outline-none focus:ring-2 focus:ring-primary/50";

// Сообщение сервера («Правильный ответ должен совпадать…») понятнее общей ошибки.
export function apiError(error, fallback) {
  const data = error?.response?.data;
  if (data && typeof data === "object") {
    const text = Object.values(data).flat().filter((v) => typeof v === "string").join(" ");
    if (text) return text;
  }
  return fallback;
}

const emptyForm = (order) => ({
  id: null,
  task_type: "story",
  title_ru: "",
  title_en: "",
  body_ru: "",
  body_en: "",
  order,
  xp_reward: 0,
  estimated_minutes: 5,
  options: ["", ""],
  correct: 0,
  starter: "",
  expected_output: "",
});

const fromTask = (task) => {
  const options = (task.data?.options || []).map((o) => o.value);
  return {
    id: task.id,
    task_type: task.task_type,
    title_ru: task.title_ru || "",
    title_en: task.title_en || "",
    body_ru: task.body_ru || "",
    body_en: task.body_en || "",
    order: task.order,
    xp_reward: task.xp_reward ?? 0,
    estimated_minutes: task.estimated_minutes ?? 5,
    options: options.length >= 2 ? options : ["", ""],
    correct: Math.max(0, options.indexOf(task.data?.correct_answer)),
    starter: task.data?.starter || "",
    expected_output: task.data?.expected_output || "",
  };
};

// null, если форма заполнена неверно (сервер проверит ещё раз).
const toPayload = (form, missionId) => {
  const payload = {
    mission: missionId,
    task_type: form.task_type,
    title_ru: form.title_ru.trim(),
    title_en: form.title_en.trim(),
    body_ru: form.body_ru,
    body_en: form.body_en,
    order: Number(form.order) || 1,
    xp_reward: Number(form.xp_reward) || 0,
    estimated_minutes: Number(form.estimated_minutes) || 5,
  };
  if (form.task_type === "quiz") {
    const answer = (form.options[form.correct] || "").trim();
    const options = form.options.map((v) => v.trim()).filter(Boolean);
    if (!answer || options.length < 2) return null;
    payload.data = {
      options: options.map((value) => ({ value, label: value })),
      correct_answer: answer,
    };
  } else if (form.task_type === "code") {
    payload.data = { starter: form.starter, expected_output: form.expected_output };
  } else {
    payload.data = {};
  }
  return payload;
};

function Field({ label, hint, children }) {
  return (
    <label className="block text-xs font-semibold text-muted">
      {label}
      <div className="mt-1 font-normal">{children}</div>
      {hint ? <span className="mt-1 block text-[11px] font-normal text-faint">{hint}</span> : null}
    </label>
  );
}

function TaskForm({ form, setForm, t }) {
  const set = (patch) => setForm({ ...form, ...patch });
  const setOption = (index, value) =>
    set({ options: form.options.map((o, i) => (i === index ? value : o)) });
  const removeOption = (index) =>
    set({
      options: form.options.filter((_, i) => i !== index),
      correct: form.correct === index ? 0 : form.correct > index ? form.correct - 1 : form.correct,
    });

  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-[10rem_1fr_1fr]">
        <Field label={t("studio.tasks.type")}>
          <select
            className={inputCls}
            value={form.task_type}
            onChange={(e) => set({ task_type: e.target.value })}
          >
            {TYPES.map((type) => (
              <option key={type} value={type}>
                {t(`studio.tasks.types.${type}`)}
              </option>
            ))}
          </select>
        </Field>
        <Field label={t("studio.tasks.titleRu")}>
          <input className={inputCls} value={form.title_ru} onChange={(e) => set({ title_ru: e.target.value })} />
        </Field>
        <Field label={t("studio.tasks.titleEn")}>
          <input className={inputCls} value={form.title_en} onChange={(e) => set({ title_en: e.target.value })} />
        </Field>
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <Field label={t("studio.tasks.bodyRu")} hint={t("studio.tasks.bodyHint")}>
          <textarea
            rows={5}
            className={inputCls}
            value={form.body_ru}
            onChange={(e) => set({ body_ru: e.target.value })}
          />
        </Field>
        <Field label={t("studio.tasks.bodyEn")}>
          <textarea
            rows={5}
            className={inputCls}
            value={form.body_en}
            onChange={(e) => set({ body_en: e.target.value })}
          />
        </Field>
      </div>

      {form.task_type === "quiz" ? (
        <fieldset className="space-y-2">
          <legend className="text-xs font-semibold text-muted">{t("studio.tasks.options")}</legend>
          {form.options.map((value, index) => (
            <div key={index} className="flex items-center gap-2">
              <input
                type="radio"
                name="correct-option"
                checked={form.correct === index}
                onChange={() => set({ correct: index })}
                aria-label={t("studio.tasks.correct")}
              />
              <input
                className={inputCls}
                value={value}
                placeholder={t("studio.tasks.optionN").replace("{n}", index + 1)}
                onChange={(e) => setOption(index, e.target.value)}
              />
              {form.options.length > 2 ? (
                <button
                  type="button"
                  onClick={() => removeOption(index)}
                  className="grid h-9 w-9 shrink-0 place-items-center rounded-lg text-muted hover:bg-error/10 hover:text-error"
                  aria-label={t("studio.editor.delete")}
                >
                  <X size={15} />
                </button>
              ) : null}
            </div>
          ))}
          <p className="text-[11px] text-faint">{t("studio.tasks.correctHint")}</p>
          {form.options.length < 8 ? (
            <Button type="button" variant="ghost" onClick={() => set({ options: [...form.options, ""] })}>
              <Plus size={15} /> {t("studio.tasks.addOption")}
            </Button>
          ) : null}
        </fieldset>
      ) : null}

      {form.task_type === "code" ? (
        <div className="grid gap-3 lg:grid-cols-2">
          <Field label={t("studio.tasks.starter")}>
            <textarea
              rows={6}
              spellCheck={false}
              className={`${inputCls} font-mono`}
              value={form.starter}
              onChange={(e) => set({ starter: e.target.value })}
            />
          </Field>
          <Field label={t("studio.tasks.expected")} hint={t("studio.tasks.expectedHint")}>
            <textarea
              rows={6}
              spellCheck={false}
              className={`${inputCls} font-mono`}
              value={form.expected_output}
              onChange={(e) => set({ expected_output: e.target.value })}
            />
          </Field>
        </div>
      ) : null}

      <div className="flex flex-wrap gap-3">
        <Field label={t("studio.editor.xp")}>
          <input
            type="number"
            min={0}
            max={100}
            className={`${inputCls} w-24`}
            value={form.xp_reward}
            onChange={(e) => set({ xp_reward: e.target.value })}
          />
        </Field>
        <Field label={t("studio.tasks.minutes")}>
          <input
            type="number"
            min={1}
            max={240}
            className={`${inputCls} w-24`}
            value={form.estimated_minutes}
            onChange={(e) => set({ estimated_minutes: e.target.value })}
          />
        </Field>
      </div>
    </div>
  );
}

// Шаги одной миссии: список, добавление, правка, порядок, удаление.
export default function StudioTasks({ missionId, t, setConfirm, onChanged }) {
  const [tasks, setTasks] = useState(null);
  const [form, setForm] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const rows = await StudioAPI.tasks.list(missionId);
      setTasks([...rows].sort((a, b) => a.order - b.order || a.id - b.id));
    } catch (e) {
      logger.error("Tasks load failed:", e);
      setError(t("studio.saveError"));
      setTasks([]);
    }
  }, [missionId, t]);

  useEffect(() => {
    load();
  }, [load]);

  const changed = async () => {
    await load();
    await onChanged();
  };

  const save = async () => {
    const payload = toPayload(form, missionId);
    if (!payload) {
      setError(t("studio.tasks.needAnswer"));
      return;
    }
    setBusy(true);
    setError("");
    try {
      if (form.id) await StudioAPI.tasks.update(form.id, payload);
      else await StudioAPI.tasks.create(payload);
      setForm(null);
      await changed();
    } catch (e) {
      logger.error("Task save failed:", e);
      setError(apiError(e, t("studio.saveError")));
    } finally {
      setBusy(false);
    }
  };

  const move = async (index, delta) => {
    const other = tasks[index + delta];
    const current = tasks[index];
    if (!other) return;
    try {
      // порядок хранится числом: меняем два шага местами (второй на случай равных значений)
      const [a, b] = current.order === other.order ? [index + 1, index + 1 + delta] : [other.order, current.order];
      await StudioAPI.tasks.update(current.id, { order: a });
      await StudioAPI.tasks.update(other.id, { order: b });
      await changed();
    } catch (e) {
      logger.error("Task move failed:", e);
      setError(t("studio.saveError"));
    }
  };

  const remove = (task) =>
    setConfirm({
      title: t("studio.tasks.confirmDeleteTitle"),
      message: t("studio.tasks.confirmDeleteMsg"),
      danger: true,
      confirmLabel: t("studio.editor.delete"),
      onConfirm: async () => {
        try {
          await StudioAPI.tasks.remove(task.id);
          await changed();
        } catch (e) {
          logger.error("Task delete failed:", e);
          setError(t("studio.saveError"));
        }
      },
    });

  if (tasks === null) {
    return <div className="ml-6 h-10 animate-pulse rounded-xl bg-panel" />;
  }

  return (
    <div className="ml-6 mt-2 space-y-2 border-l-2 border-border pl-3">
      {error ? (
        <p role="alert" className="rounded-lg border border-error/30 bg-error/10 px-3 py-2 text-xs text-error">
          {error}
        </p>
      ) : null}

      {tasks.length === 0 && !form ? (
        <p className="text-xs text-muted">{t("studio.tasks.empty")}</p>
      ) : null}

      {tasks.map((task, index) => {
        if (form && form.id === task.id) return null;
        const Icon = ICONS[task.task_type] || BookOpen;
        return (
          <div
            key={task.id}
            className="flex items-center gap-2 rounded-xl border border-border bg-panel/40 px-3 py-2"
          >
            <Icon size={15} className="shrink-0 text-muted" aria-hidden="true" />
            <span className="w-6 shrink-0 text-xs tabular-nums text-faint">{index + 1}</span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm text-text">{task.title_ru || task.title_en || "—"}</p>
              <p className="text-[11px] text-muted">{t(`studio.tasks.types.${task.task_type}`)}</p>
            </div>
            <button
              type="button"
              onClick={() => move(index, -1)}
              disabled={index === 0}
              className="grid h-8 w-8 place-items-center rounded-lg text-muted hover:bg-panel hover:text-text disabled:opacity-30"
              aria-label={t("studio.tasks.moveUp")}
            >
              <ArrowUp size={14} />
            </button>
            <button
              type="button"
              onClick={() => move(index, 1)}
              disabled={index === tasks.length - 1}
              className="grid h-8 w-8 place-items-center rounded-lg text-muted hover:bg-panel hover:text-text disabled:opacity-30"
              aria-label={t("studio.tasks.moveDown")}
            >
              <ArrowDown size={14} />
            </button>
            <button
              type="button"
              onClick={() => {
                setError("");
                setForm(fromTask(task));
              }}
              className="grid h-8 w-8 place-items-center rounded-lg text-muted hover:bg-panel hover:text-text"
              aria-label={t("studio.editor.edit")}
            >
              <Pencil size={14} />
            </button>
            <button
              type="button"
              onClick={() => remove(task)}
              className="grid h-8 w-8 place-items-center rounded-lg text-muted hover:bg-error/10 hover:text-error"
              aria-label={t("studio.editor.delete")}
            >
              <Trash2 size={14} />
            </button>
          </div>
        );
      })}

      {form ? (
        <div className="rounded-xl border border-border bg-panel/60 p-3">
          <TaskForm form={form} setForm={setForm} t={t} />
          <div className="mt-3 flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => setForm(null)}>
              {t("studio.editor.cancel")}
            </Button>
            <Button type="button" onClick={save} disabled={busy}>
              <Check size={16} />
              {busy ? t("studio.editor.saving") : t("studio.editor.save")}
            </Button>
          </div>
        </div>
      ) : (
        <Button
          type="button"
          variant="outline"
          onClick={() => {
            setError("");
            setForm(emptyForm((tasks.at(-1)?.order ?? 0) + 1));
          }}
        >
          <Plus size={15} /> {t("studio.tasks.add")}
        </Button>
      )}
    </div>
  );
}
