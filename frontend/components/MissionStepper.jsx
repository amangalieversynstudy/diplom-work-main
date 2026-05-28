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
        const locked = task.is_required && index > 0 && !progressMap[tasks[index - 1].id]?.status;

        return (
          <button
            key={task.id}
            onClick={() => !locked && onSelect?.(task.id)}
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
