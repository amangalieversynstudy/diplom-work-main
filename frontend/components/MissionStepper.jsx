import { BookOpen, CheckCircle2, Code2, HelpCircle, ShieldHalf } from "lucide-react";

const cx = (...classes) => classes.filter(Boolean).join(" ");

const iconMap = {
  story: BookOpen,
  quiz: HelpCircle,
  code: Code2,
  project: ShieldHalf,
  challenge: ShieldHalf,
};

export default function MissionStepper({
  tasks = [],
  activeTaskId,
  progressMap = {},
  onSelect,
  labels = {},
}) {
  if (!tasks.length) return null;
  const steps = labels.steps || {};
  const mainLabel = labels.mainStep || "Main step";
  const sideLabel = labels.sideQuest || "Side quest";
  const minutesLabel = labels.minutes || "min";
  return (
    <div className="space-y-3">
      {tasks.map((task, index) => {
        const Icon = iconMap[task.task_type] || BookOpen;
        const progress = progressMap[task.id];
        const completed = progress?.status === "completed";
        const current = task.id === activeTaskId;
        const locked = task.is_required && index > 0 && !progressMap[tasks[index - 1].id]?.status;
        return (
          <button
            key={task.id}
            onClick={() => !locked && onSelect?.(task.id)}
            className={cx(
              "w-full flex items-center gap-3 rounded-xl border px-4 py-3 text-left transition",
              locked && "opacity-50 cursor-not-allowed",
              current && "border-white/80 bg-white/5",
              !current && !locked && "border-white/10 bg-white/2 hover:border-white/40"
            )}
            type="button"
          >
            <span
              className={cx(
                "h-10 w-10 flex items-center justify-center rounded-full border",
                completed ? "bg-emerald-500/10 border-emerald-400 text-emerald-300" : "border-white/20 text-white/70"
              )}
            >
              {completed ? <CheckCircle2 size={20} /> : <Icon size={20} />}
            </span>
            <div className="flex-1">
              <p className="text-xs uppercase tracking-[0.3em] text-white/60">
                {(steps[task.task_type] || task.task_type).toUpperCase()} · {task.estimated_minutes || 5} {minutesLabel}
              </p>
              <p className="font-semibold text-white">{task.title || task.title_ru || task.title_en}</p>
              <p className="text-xs text-white/60">
                {task.is_side_quest ? sideLabel : mainLabel}
              </p>
            </div>
            <p className="text-sm text-gold font-semibold">+{task.xp_reward || 0} XP</p>
          </button>
        );
      })}
    </div>
  );
}
