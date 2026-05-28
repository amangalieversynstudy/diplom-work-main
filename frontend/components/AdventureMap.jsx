import { motion } from "framer-motion";

// Словарь стилей для разных классов проекта (python / django / devops)
const classThemes = {
  python: {
    // Python-спеллблейд — золотисто-фиолетовая магия
    bg: "bg-gradient-to-br from-purple-900/40 via-[#1e1e1e] to-[#0f0f11]",
    lineStroke: "#a855f7",
    nodeBase: "bg-purple-500/20 border-purple-500/50",
    nodeGlow: "shadow-[0_0_15px_rgba(168,85,247,0.35)]",
  },
  django: {
    // Арканист Django — изумрудный
    bg: "bg-gradient-to-br from-emerald-900/40 via-[#1e1e1e] to-[#0f0f11]",
    lineStroke: "#10b981",
    nodeBase: "bg-emerald-500/20 border-emerald-500/50",
    nodeGlow: "shadow-[0_0_15px_rgba(16,185,129,0.35)]",
  },
  devops: {
    // DevOps-рейнджер — циан/металл
    bg: "bg-gradient-to-br from-cyan-900/40 via-[#1e1e1e] to-[#0f0f11]",
    lineStroke: "#06b6d4",
    nodeBase: "bg-cyan-500/20 border-cyan-500/50",
    nodeGlow: "shadow-[0_0_15px_rgba(6,182,212,0.35)]",
  },
  default: {
    bg: "bg-[#141418]",
    lineStroke: "#6b7280",
    nodeBase: "bg-gray-500/20 border-gray-500/50",
    nodeGlow: "",
  },
};

function Node({ node, delay = 0, theme }) {
  const isLocked = node.status === "locked";
  const isCompleted = node.status === "completed";

  // Стилизуем узлы в зависимости от их статуса и темы класса
  let nodeStyle = theme.nodeBase;
  if (isCompleted) nodeStyle = "bg-yellow-500/20 border-yellow-500/80 shadow-[0_0_10px_rgba(234,179,8,0.4)]";
  else if (!isLocked) nodeStyle = `bg-[#1e1e1e] border-white ${theme.nodeGlow}`;

  // Туман войны для locked-узлов: opacity 0.4 + blur,
  // на hover/focus снимаем эффект — узел остаётся доступен глазу и клавиатуре
  const fogClass = isLocked
    ? "opacity-40 blur-[2px] hover:opacity-100 hover:blur-0 focus-visible:opacity-100 focus-visible:blur-0"
    : "";

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.8 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay }}
      tabIndex={0}
      className={`absolute w-12 h-12 -ml-6 -mt-6 rounded-full border-2 flex items-center justify-center cursor-pointer transition-all duration-300 hover:scale-110 ${nodeStyle} ${fogClass}`}
      style={{
        left: `${node.x}%`,
        top: `${node.y}%`,
      }}
      title={node.title}
    >
      <span className="text-xs font-bold text-white">
        {node.id}
      </span>
    </motion.div>
  );
}

export default function AdventureMap({ nodes, playerClass }) {
  // Определяем тему, приводя класс к нижнему регистру (или берем дефолт)
  const normalizedClass = playerClass ? playerClass.toLowerCase() : "default";
  const theme = classThemes[normalizedClass] || classThemes.default;

  return (
    // Внешняя оболочка: горизонтальный скролл при узком viewport,
    // padding по краям чтобы крайние узлы (x≈0/100%) не упирались в борт,
    // overscroll-behavior-x чтобы свайп карты не триггерил back-навигацию.
    <div
      className="w-full overflow-x-auto overflow-y-hidden adventure-map-scroll"
      style={{ overscrollBehaviorX: "contain" }}
    >
      <div
        className={`relative h-[600px] min-w-[900px] mx-2 px-6 border border-[#333] rounded-xl shadow-2xl overflow-hidden ${theme.bg}`}
      >
        {/* SVG-линии между нодами */}
        <svg className="absolute inset-0 w-full h-full pointer-events-none">
          {nodes.map((node, i) => {
            if (i === 0) return null;
            const prev = nodes[i - 1];
            return (
              <motion.line
                key={`line-${node.id}`}
                x1={`${prev.x}%`}
                y1={`${prev.y}%`}
                x2={`${node.x}%`}
                y2={`${node.y}%`}
                stroke={theme.lineStroke}
                strokeWidth="2"
                strokeDasharray="4 4"
                initial={{ pathLength: 0 }}
                animate={{ pathLength: 1 }}
                transition={{ duration: 1, delay: i * 0.2 }}
              />
            );
          })}
        </svg>

        {/* Сами ноды */}
        {nodes.map((node, i) => (
          <Node key={node.id} node={node} delay={i * 0.2} theme={theme} />
        ))}
      </div>
    </div>
  );
}