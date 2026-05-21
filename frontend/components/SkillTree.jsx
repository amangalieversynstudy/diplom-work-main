import { motion } from "framer-motion";
import { Code, ServerCog, Share2, Lock, Check, Sparkles } from "lucide-react";

// Backend ClassRole pk → node definition. Must match dictionaries/ru.js.
const NODES = {
  1: {
    id: 1,
    key: "python",
    name: "Python-спеллблейд",
    focus: "Базовая магия",
    desc: "Стартовый класс. Скрипты, алгоритмы, основа любой магии.",
    icon: Code,
    crest: "🐍",
    tier: 0,
  },
  2: {
    id: 2,
    key: "django",
    name: "Арканист Django",
    focus: "Контроль backend",
    desc: "Продвинутая ветка: ORM, DRF, серверная магия.",
    icon: ServerCog,
    crest: "🛡️",
    tier: 1,
  },
  3: {
    id: 3,
    key: "devops",
    name: "DevOps-рейнджер",
    focus: "Деплой и инфра",
    desc: "Продвинутая ветка: Docker, CI/CD, мультиоблака.",
    icon: Share2,
    crest: "⚙️",
    tier: 1,
  },
};

// Edges: parent pk → list of child pks. Python (pk=1) is the root; django and devops branch from it.
const EDGES = [
  { from: 1, to: 2 },
  { from: 1, to: 3 },
];

function nodeState(node, currentClassId) {
  if (!currentClassId) return "available";
  if (node.id === currentClassId) return "current";
  // If current is a tier-1 class, root (python) is considered completed
  if (node.tier === 0 && currentClassId !== node.id) return "completed";
  // Other tier-1 nodes are available paths
  if (node.tier === 1) return "available";
  return "available";
}

const STATE_STYLES = {
  current: {
    card: "border-primary bg-primary/10 shadow-[0_0_30px_var(--primary-selection)]",
    icon: "bg-primary text-white",
    label: "ТЕКУЩИЙ ПУТЬ",
    labelColor: "text-primary",
    badge: Sparkles,
  },
  completed: {
    card: "border-primary/40 bg-surface",
    icon: "bg-primary/80 text-white",
    label: "ПРОЙДЕНО",
    labelColor: "text-primary/70",
    badge: Check,
  },
  available: {
    card: "border-border bg-surface opacity-70 hover:opacity-100 transition-opacity",
    icon: "bg-panel text-muted border border-border",
    label: "ДОСТУПНО",
    labelColor: "text-muted",
    badge: null,
  },
  locked: {
    card: "border-border bg-panel opacity-40",
    icon: "bg-panel text-muted",
    label: "ЗАБЛОКИРОВАНО",
    labelColor: "text-muted",
    badge: Lock,
  },
};

function SkillNode({ node, state }) {
  const styles = STATE_STYLES[state];
  const Icon = node.icon;
  const Badge = styles.badge;

  return (
    <motion.div
      whileHover={{ scale: state === "locked" ? 1 : 1.03, y: state === "locked" ? 0 : -4 }}
      transition={{ type: "spring", stiffness: 300, damping: 22 }}
      className={`relative w-full max-w-[260px] rounded-2xl border-2 p-5 ${styles.card}`}
    >
      <div className="flex items-center gap-3 mb-3">
        <div
          className={`w-12 h-12 rounded-xl flex items-center justify-center text-2xl ${styles.icon}`}
        >
          <span>{node.crest}</span>
        </div>
        <div className="flex-1 min-w-0">
          <p className={`text-[10px] font-bold uppercase tracking-widest ${styles.labelColor}`}>
            {styles.label}
          </p>
          <h4 className="text-sm font-display font-bold text-text truncate">{node.name}</h4>
        </div>
        {Badge && (
          <div className="w-7 h-7 rounded-full bg-primary/15 flex items-center justify-center">
            <Badge size={14} className="text-primary" />
          </div>
        )}
      </div>
      <div className="flex items-center gap-2 text-xs text-muted mb-2">
        <Icon size={14} className="text-accent" />
        <span className="uppercase tracking-wider font-semibold text-accent">{node.focus}</span>
      </div>
      <p className="text-xs text-muted leading-relaxed">{node.desc}</p>
    </motion.div>
  );
}

export default function SkillTree({ currentClassId }) {
  const root = NODES[1];
  const children = EDGES.filter((e) => e.from === root.id).map((e) => NODES[e.to]);

  const rootState = nodeState(root, currentClassId);

  return (
    <div className="bg-surface border border-border rounded-3xl p-6 md:p-8 shadow-sm">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-xl font-bold text-text flex items-center gap-2">
            <Sparkles size={20} className="text-primary" />
            Древо Навыков
          </h3>
          <p className="text-xs text-muted mt-1">Твой путь героя через классы и специализации</p>
        </div>
      </div>

      <div className="relative flex flex-col items-center gap-10 pt-2 pb-2">
        {/* Root node */}
        <SkillNode node={root} state={rootState} />

        {/* Connector lines (SVG) */}
        <svg
          className="absolute left-0 right-0 mx-auto pointer-events-none"
          style={{ top: "165px", height: "60px", width: "100%" }}
          viewBox="0 0 400 60"
          preserveAspectRatio="none"
        >
          <line
            x1="200"
            y1="0"
            x2="80"
            y2="60"
            stroke="var(--primary)"
            strokeWidth="2"
            strokeDasharray="4 4"
            opacity="0.4"
          />
          <line
            x1="200"
            y1="0"
            x2="320"
            y2="60"
            stroke="var(--primary)"
            strokeWidth="2"
            strokeDasharray="4 4"
            opacity="0.4"
          />
        </svg>

        {/* Children nodes */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 w-full max-w-[600px]">
          {children.map((child) => (
            <div key={child.id} className="flex justify-center">
              <SkillNode node={child} state={nodeState(child, currentClassId)} />
            </div>
          ))}
        </div>
      </div>

      <p className="text-[11px] text-muted text-center mt-6 italic">
        MVP: визуализация прогрессии. Полная разблокировка ветвей — в следующем апдейте.
      </p>
    </div>
  );
}
