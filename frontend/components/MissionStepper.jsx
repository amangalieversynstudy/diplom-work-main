import { FileText, CheckCircle2, Code2, HelpCircle, Lock } from "lucide-react";

const cx = (...classes) => classes.filter(Boolean).join(" ");

const iconMap = {
  story: FileText,
  quiz: HelpCircle,
  code: Code2,
};

const colorMap = {
  story: "text-[#519aba]",
  quiz: "text-[#cca700]",
  code: "text-[#89d185]",
};

export default function MissionStepper({
  tasks = [],
  activeTaskId,
  progressMap = {},
  onSelect,
}) {
  if (!tasks.length) return null;

  return (
    <div className="flex flex-col py-1">
      {tasks.map((task, index) => {
        const Icon = iconMap[task.task_type] || FileText;
        const colorClass = colorMap[task.task_type] || "text-[#cccccc]";
        const progress = progressMap[task.id];
        const completed = progress?.status === "completed";
        const current = task.id === activeTaskId;
        const locked = task.is_required && index > 0 && !progressMap[tasks[index - 1].id]?.status;

        return (
          <button
            key={task.id}
            onClick={() => !locked && onSelect?.(task.id)}
            className={cx(
              "w-full flex items-center justify-between px-6 py-1.5 text-[13px] text-left transition-colors",
              locked ? "opacity-40 cursor-not-allowed" : "cursor-pointer",
              current ? "bg-[#37373d] text-white" : "text-[#cccccc] hover:bg-[#2a2d2e]"
            )}
            type="button"
          >
            <div className="flex items-center gap-2 truncate">
              {locked ? <Lock size={14} className="text-[#858585]" /> : <Icon size={14} className={colorClass} />}
              <span className={`truncate ${current ? "font-medium" : ""}`}>{task.title || task.title_ru || task.title_en}</span>
            </div>
            {completed && <CheckCircle2 size={12} className="text-[#89d185] shrink-0 ml-2" />}
          </button>
        );
      })}
    </div>
  );
}
