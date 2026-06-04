import { motion } from "framer-motion";
import Link from "next/link";
import { Lock, CheckCircle, Compass, ChevronRight } from "lucide-react";
import { missionStatus } from "../lib/api";
import { useI18n } from "../lib/i18n";

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
  // Статус берём из DRF-полей миссии (user_progress/available),
  // т.к. сериализатор не отдаёт плоское поле status.
  const status = missionStatus(node);
  const isLocked = status === "locked";
  const isCompleted = status === "completed";

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
        left: `${node.pos_x}%`,
        top: `${node.pos_y}%`,
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
  const { t, language } = useI18n();
  // Определяем тему, приводя класс к нижнему регистру (или берем дефолт)
  const normalizedClass = playerClass ? playerClass.toLowerCase() : "default";
  const theme = classThemes[normalizedClass] || classThemes.default;

  return (
    <>
    {/* Десктоп: интерактивная карта-схема. Горизонтальный скролл при узком
        viewport, overscroll-behavior-x чтобы свайп карты не триггерил
        back-навигацию. На тач-экранах (<lg) скрыта — узлы раскрывают подпись
        только по hover, поэтому ниже отдаём тапабельный список. */}
    <div
      className="hidden lg:block w-full overflow-x-auto overflow-y-hidden adventure-map-scroll"
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
                x1={`${prev.pos_x}%`}
                y1={`${prev.pos_y}%`}
                x2={`${node.pos_x}%`}
                y2={`${node.pos_y}%`}
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

    {/* Мобильный список миссий: на тач-экранах карта-схема нечитаема
        (подписи узлов только по hover, нужен горизонтальный скролл),
        поэтому показываем простой тапабельный список со статусом. */}
    <div className="lg:hidden">
      {nodes.length === 0 ? (
        <div className="text-center text-muted py-10 font-mono text-sm">
          {t("worldsPage.mapEmpty")}
        </div>
      ) : (
        <ol className="space-y-3">
          {nodes.map((node) => {
            const status = missionStatus(node);
            const isCompleted = status === "completed";
            const isLocked = status === "locked";
            const Icon = isCompleted ? CheckCircle : isLocked ? Lock : Compass;
            const title =
              (language === "en"
                ? node.title_en || node.title_ru
                : node.title_ru || node.title_en) ||
              node.title ||
              t("worldsPage.missionFallback");
            const statusLabel = isCompleted
              ? t("worldsPage.statusCompleted")
              : isLocked
              ? t("worldsPage.statusLocked")
              : t("worldsPage.statusAvailable");
            return (
              <li key={node.id}>
                <Link
                  href={isLocked ? "#" : `/missions/${node.id}`}
                  onClick={(e) => isLocked && e.preventDefault()}
                  aria-disabled={isLocked}
                  className={`flex items-center gap-3 rounded-2xl border p-3 transition-colors ${
                    isLocked
                      ? "border-border bg-panel/60 opacity-70 cursor-default"
                      : "border-border bg-surface hover:border-primary/50 active:scale-[0.99]"
                  }`}
                >
                  <span
                    className={`grid h-11 w-11 shrink-0 place-items-center rounded-xl border ${
                      isCompleted
                        ? "bg-emerald-500/15 border-emerald-500/40 text-emerald-400"
                        : isLocked
                        ? "bg-panel border-border text-muted"
                        : "bg-primary/10 border-primary/30 text-primary"
                    }`}
                  >
                    <Icon size={20} strokeWidth={2.2} />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-bold text-text">
                      {title}
                    </span>
                    <span className="block text-[11px] font-bold uppercase tracking-widest text-muted mt-0.5">
                      {statusLabel}
                    </span>
                  </span>
                  {!isLocked && (
                    <ChevronRight size={18} className="shrink-0 text-muted" />
                  )}
                </Link>
              </li>
            );
          })}
        </ol>
      )}
    </div>
    </>
  );
}