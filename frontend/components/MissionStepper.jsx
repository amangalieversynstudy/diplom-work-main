import { useEffect, useRef } from "react";
import { FileText, CheckCircle2, Code2, HelpCircle, Lock } from "lucide-react";

const cx = (...classes) => classes.filter(Boolean).join(" ");

const iconMap = {
  story: FileText,
  quiz: HelpCircle,
  code: Code2,
};

// Цветовые палитры по варианту: dark — VS Code эстетика, parchment —
// тёплая «бумажная» палитра под пергаментный фон квест-панели.
const variantStyles = {
  dark: {
    color: { story: "text-[#519aba]", quiz: "text-[#cca700]", code: "text-[#89d185]", default: "text-[#cccccc]" },
    item: "text-[#cccccc]",
    itemHover: "hover:bg-[#2a2d2e]",
    itemActive: "bg-[#37373d] text-white",
    completed: "text-[#89d185]",
    locked: "text-[#858585]",
  },
  parchment: {
    color: { story: "text-[#8b5a2b]", quiz: "text-[#a16207]", code: "text-[#6b8e23]", default: "text-[#3e2723]" },
    item: "text-[#3e2723]",
    itemHover: "hover:bg-[#5c3a21]/15",
    itemActive: "bg-[#5c3a21]/25 text-[#3e2723] font-semibold",
    completed: "text-[#6b8e23]",
    locked: "text-[#8b5a2b]/60",
  },
};

// Same rule as the server: a step opens once every earlier required step is solved.
export function isStepLocked(tasks, index, progressMap) {
  return tasks
    .slice(0, index)
    .some((earlier) => earlier.is_required && progressMap[earlier.id]?.status !== "completed");
}

export default function MissionStepper({
  tasks = [],
  activeId,
  progress: progressMap = {},
  onSelect,
  variant = "dark",
}) {
  if (!tasks.length) return null;
  const v = variantStyles[variant] || variantStyles.dark;

  return (
    <div className="flex flex-col py-1">
      {tasks.map((task, index) => {
        const Icon = iconMap[task.task_type] || FileText;
        const colorClass = v.color[task.task_type] || v.color.default;
        const taskProg = progressMap[task.id];
        const completed = taskProg?.status === "completed";
        const current = task.id === activeId;
        const locked = isStepLocked(tasks, index, progressMap);

        return (
          <button
            key={task.id}
            onClick={() => !locked && onSelect?.(task.id)}
            disabled={locked}
            aria-disabled={locked}
            aria-current={current ? "step" : undefined}
            className={cx(
              "w-full flex items-center justify-between px-6 py-1.5 text-[13px] text-left transition-colors rounded-md",
              locked ? "opacity-40 cursor-not-allowed" : "cursor-pointer",
              current ? v.itemActive : `${v.item} ${v.itemHover}`
            )}
            type="button"
          >
            <div className="flex items-center gap-2 truncate">
              {locked ? <Lock size={14} className={v.locked} /> : <Icon size={14} className={colorClass} />}
              <span className={`truncate ${current ? "font-medium" : ""}`}>{task.title || task.title_ru || task.title_en}</span>
            </div>
            {completed && <CheckCircle2 size={12} className={`${v.completed} shrink-0 ml-2`} />}
          </button>
        );
      })}
    </div>
  );
}

// Телефон: те же шаги, но полоской с крупными кнопками (44 px) вместо списка свитков.
export function StepStrip({ tasks = [], activeId, progress: progressMap = {}, onSelect, label }) {
  const listRef = useRef(null);

  // активный шаг всегда в поле зрения полосы (сама страница при этом не прокручивается)
  useEffect(() => {
    const list = listRef.current;
    const item = list?.querySelector('[aria-current="step"]');
    if (!list || !item) return;
    const left = item.offsetLeft - (list.clientWidth - item.offsetWidth) / 2;
    list.scrollTo({ left: Math.max(0, left) });
  }, [activeId, tasks.length]);

  if (!tasks.length) return null;

  return (
    <ol ref={listRef} aria-label={label} className="flex gap-2 overflow-x-auto pb-1">
      {tasks.map((task, index) => {
        const Icon = iconMap[task.task_type] || FileText;
        const completed = progressMap[task.id]?.status === "completed";
        const current = task.id === activeId;
        const locked = isStepLocked(tasks, index, progressMap);
        const title = task.title || task.title_ru || task.title_en || "";
        return (
          <li key={task.id} className="shrink-0">
            <button
              type="button"
              disabled={locked}
              aria-current={current ? "step" : undefined}
              aria-label={`${index + 1}. ${title}`}
              onClick={() => onSelect?.(task.id)}
              className={cx(
                "relative grid h-11 w-11 place-items-center rounded-xl border-2 transition-colors",
                current
                  ? "border-[#fde68a] bg-[#5c3a21] text-[#fde68a]"
                  : completed
                  ? "border-[#6b8e23]/70 bg-[#2b1d11] text-[#a3e635]"
                  : "border-[#8b5a2b]/60 bg-[#2b1d11] text-[#d4a24c]",
                locked && "opacity-40"
              )}
            >
              {locked ? <Lock size={16} /> : <Icon size={18} />}
              <span className="absolute -left-1 -top-1 grid h-4 min-w-[1rem] place-items-center rounded-full bg-[#fde68a] px-1 font-mono text-[10px] font-bold leading-none text-[#2b1d11]">
                {index + 1}
              </span>
              {completed && !locked && (
                <CheckCircle2
                  size={14}
                  aria-hidden="true"
                  className="absolute -bottom-1 -right-1 rounded-full bg-[#2b1d11] text-[#a3e635]"
                />
              )}
            </button>
          </li>
        );
      })}
    </ol>
  );
}
