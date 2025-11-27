import { CheckCircle2, Lock, Circle } from "lucide-react";

const styles = {
  completed: "bg-success/10 text-success border-success/30 shadow-inner",
  available: "bg-primary/10 text-primary border-primary/30",
  locked: "bg-white/5 text-white/70 border-white/20",
};

const icons = {
  completed: CheckCircle2,
  available: Circle,
  locked: Lock,
};

export default function Badge({ status = "available", children }) {
  const Icon = icons[status] || Circle;
  return (
    <span
      className={`inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border backdrop-blur ${
        styles[status]
      }`}
    >
      <Icon size={14} />
      {children}
    </span>
  );
}
