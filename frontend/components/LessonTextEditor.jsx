import { useRef } from "react";
import { Bold, Code2, Heading, LayoutTemplate, List, ListOrdered, MessageSquareWarning, SquareCode } from "lucide-react";
import { storyToHtml } from "../lib/story";
import { sanitizeHtml } from "../lib/sanitize";

// Текст урока без HTML: преподаватель пишет обычным текстом, кнопки вставляют простую разметку
// (lib/story.js), а ниже сразу видно, как урок увидит ученик (тот же разбор и те же стили .story-body).
const TOOLS = [
  { id: "heading", icon: Heading, before: "## ", line: true },
  { id: "bold", icon: Bold, before: "**", after: "**" },
  { id: "code", icon: Code2, before: "`", after: "`" },
  { id: "codeBlock", icon: SquareCode, before: "```\n", after: "\n```", block: true },
  { id: "list", icon: List, before: "- ", line: true },
  { id: "numbered", icon: ListOrdered, before: "1. ", line: true },
  { id: "note", icon: MessageSquareWarning, line: true },
];

// Заготовки текста урока: структура, которую остаётся заполнить своими словами.
export const LESSON_SKELETONS = {
  ru: {
    theory:
      "## Что узнаем\nОдной фразой: чему научится ученик.\n\n## Объяснение\nКороткое объяснение своими словами.\n\n```\n# пример кода\nprint(\"Привет\")\n```\n\nВажно: одна вещь, которую легко забыть.",
    task:
      "## Задание\nЧто нужно сделать — одним-двумя предложениями.\n\n## Что должно получиться\n- программа выводит …\n- значение хранится в переменной …\n\nСовет: с чего начать.",
    story:
      "## Сюжет\nКороткая история: кто герой и что ему нужно.\n\nЧтобы помочь герою, нужно:\n1. …\n2. …\n\n> Цитата или подсказка наставника.",
  },
  en: {
    theory:
      "## What we learn\nOne sentence: what the learner will be able to do.\n\n## Explanation\nA short explanation in your own words.\n\n```\n# code sample\nprint(\"Hello\")\n```\n\nNote: one thing that is easy to forget.",
    task:
      "## Task\nWhat to do, in one or two sentences.\n\n## Expected result\n- the program prints …\n- the value is kept in the variable …\n\nTip: where to start.",
    story:
      "## Story\nA short story: who the hero is and what they need.\n\nTo help the hero:\n1. …\n2. …\n\n> A quote or a hint from the mentor.",
  },
};

export default function LessonTextEditor({ id, label, value, onChange, lang = "ru", t }) {
  const ref = useRef(null);
  const noteLabel = lang === "en" ? "Note" : "Важно";

  const apply = (tool) => {
    const el = ref.current;
    if (!el) return;
    const start = el.selectionStart ?? value.length;
    const end = el.selectionEnd ?? value.length;
    const before = tool.id === "note" ? `${noteLabel}: ` : tool.before;
    const after = tool.after || "";
    const selected = value.slice(start, end) || t(`studio.tasks.text.samples.${tool.id}`);
    // заголовок, список и блок кода начинаются с новой строки
    let prefix = "";
    if ((tool.line || tool.block) && start > 0 && value[start - 1] !== "\n") prefix = "\n";
    if (tool.block && start > 0) prefix = value.slice(start - 2, start) === "\n\n" ? "" : prefix + "\n";
    const next = value.slice(0, start) + prefix + before + selected + after + value.slice(end);
    onChange(next);
    const from = start + prefix.length + before.length;
    requestAnimationFrame(() => {
      el.focus();
      el.setSelectionRange(from, from + selected.length);
    });
  };

  const insertSkeleton = (kind) => {
    const skeleton = (LESSON_SKELETONS[lang] || LESSON_SKELETONS.ru)[kind];
    if (!skeleton) return;
    onChange(value.trim() ? `${value.trimEnd()}\n\n${skeleton}` : skeleton);
  };

  const html = sanitizeHtml(storyToHtml(value));

  return (
    <div className="space-y-2">
      <span className="block text-xs font-semibold text-muted">{label}</span>
      <div role="toolbar" aria-label={t("studio.tasks.text.toolbar")} className="flex flex-wrap items-center gap-1">
        {TOOLS.map(({ id: toolId, icon: Icon }) => (
          <button
            key={toolId}
            type="button"
            onClick={() => apply(TOOLS.find((tool) => tool.id === toolId))}
            title={t(`studio.tasks.text.tools.${toolId}`)}
            aria-label={t(`studio.tasks.text.tools.${toolId}`)}
            className="grid h-8 w-8 place-items-center rounded-lg border border-border text-muted hover:bg-surface hover:text-text"
          >
            <Icon size={15} aria-hidden="true" />
          </button>
        ))}
        <label className="ml-1 flex items-center gap-1 text-xs text-muted">
          <LayoutTemplate size={14} aria-hidden="true" />
          <select
            className="rounded-lg border border-border bg-panel px-2 py-1 text-xs text-text"
            value=""
            onChange={(event) => insertSkeleton(event.target.value)}
            aria-label={t("studio.tasks.text.skeleton")}
          >
            <option value="">{t("studio.tasks.text.skeleton")}</option>
            {Object.keys(LESSON_SKELETONS.ru).map((kind) => (
              <option key={kind} value={kind}>
                {t(`studio.tasks.text.skeletons.${kind}`)}
              </option>
            ))}
          </select>
        </label>
      </div>
      <textarea
        id={id}
        ref={ref}
        rows={7}
        className="w-full rounded-xl border border-border bg-panel px-3.5 py-2.5 font-mono text-sm text-text placeholder:text-faint focus:outline-none focus:ring-2 focus:ring-primary/50"
        value={value}
        placeholder={t("studio.tasks.text.placeholder")}
        onChange={(event) => onChange(event.target.value)}
      />
      <p className="text-xs text-muted">{t("studio.tasks.bodyHint")}</p>
      <div className="scroll-frame p-3">
        <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-muted">{t("studio.tasks.text.preview")}</p>
        {html ? (
          <div className="story-body text-sm" dangerouslySetInnerHTML={{ __html: html }} />
        ) : (
          <p className="text-sm italic text-faint">{t("studio.tasks.text.previewEmpty")}</p>
        )}
      </div>
    </div>
  );
}
