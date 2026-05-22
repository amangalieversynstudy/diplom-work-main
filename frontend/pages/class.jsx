import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import { motion } from "framer-motion";
import Layout from "../components/Layout";
import Button from "../components/Button";
import ConfirmModal from "../components/ConfirmModal";
import { setPlayerClass, getPlayerClass, fetchIntroStatus } from "../lib/class";
import { Profile } from "../lib/api";
import { toast } from "sonner";
import { Code, ServerCog, Share2, Lock, Sparkles, Check } from "lucide-react";
import { useDictionary } from "../lib/i18n";
import logger from "../lib/logger";

// Frontend id → backend ClassRole pk (must match fixtures/class_roles.json)
const CLASS_ROLE_IDS = { python: 1, django: 2, devops: 3 };

const ICONS = { python: Code, django: ServerCog, devops: Share2 };

// Skill-tree topology. tier=0 is root (Python). Branches require Python first
// — но если у игрока УЖЕ выбран класс, открываем все ветви для свободной смены.
const TREE = [
  { id: "python", tier: 0, locked: false },
  { id: "django", tier: 1, locked: true },
  { id: "devops", tier: 1, locked: true },
];

export default function ChooseClassPage() {
  const dict = useDictionary();
  const router = useRouter();
  const [introStatus, setIntroStatus] = useState({ loading: true, locked: false, data: null });
  const [choosing, setChoosing] = useState(false);
  const [currentClass, setCurrentClass] = useState(null); // выбранный класс игрока
  const [confirmData, setConfirmData] = useState(null); // RPG-confirm вместо window.confirm

  useEffect(() => {
    // Запоминаем текущий класс, но НЕ редиректим — даём свободно сменить.
    setCurrentClass(getPlayerClass());

    let cancelled = false;
    fetchIntroStatus().then((data) => {
      if (cancelled) return;
      if (!data) {
        setIntroStatus({ loading: false, locked: false, data: null });
        return;
      }
      setIntroStatus({ loading: false, locked: !data.class_unlocked, data });
    });
    return () => {
      cancelled = true;
    };
  }, []);

  // Если класс уже выбран — игрок прошёл порог входа, разрешаем все ветви.
  const hasClass = Boolean(currentClass);

  async function choose(id) {
    const node = TREE.find((n) => n.id === id);
    if (!node || choosing) return;
    // Залочена только если у игрока ЕЩЁ нет класса (т.е. он впервые на странице).
    if (node.locked && !hasClass) return;
    // Если кликнули по уже выбранному — просто уходим в профиль, без запроса.
    if (id === currentClass) {
      router.push("/profile");
      return;
    }

    // ── МЯГКАЯ РЕКОМЕНДАЦИЯ (Soft-lock) ──
    // Показываем confirm только при ПЕРВОМ выборе. При смене класса лишний
    // диалог не нужен — игрок уже в игре и знает, что делает.
    if (introStatus.locked && !hasClass) {
      setConfirmData({
        title: "Сначала Вводный курс?",
        message:
          "Академия настоятельно рекомендует пройти Вводный курс — он даст базовые навыки магии. Точно хочешь выбрать класс прямо сейчас?",
        confirmLabel: "Да, выбрать сейчас",
        cancelLabel: "К вводному курсу",
        onConfirm: () => performChoose(id),
        onCancel: () => router.push("/worlds"),
      });
      return;
    }
    performChoose(id);
  }

  async function performChoose(id) {
    setChoosing(true);
    try {
      const classRoleId = CLASS_ROLE_IDS[id];
      if (classRoleId) {
        await Profile.update({ class_role: classRoleId });
      }
      setPlayerClass(id);
      setCurrentClass(id);
      const successMsg = hasClass
        ? "Класс изменён! Новые силы пробуждаются..."
        : dict.classPage?.toastSuccess || "Класс успешно выбран!";
      toast.success(successMsg, { duration: 3000 });
      router.push("/profile");
    } catch (e) {
      // Умная обработка ошибки бэкенда (на случай пустой БД)
      logger.error("Ошибка сервера:", e.response?.data);
      let errorMsg = "Не удалось сохранить класс. Попробуй ещё раз.";
      if (e.response?.data) {
        const data = e.response.data;
        if (data.class_role) {
          errorMsg = Array.isArray(data.class_role) ? data.class_role[0] : data.class_role;
        } else if (data.detail) {
          errorMsg = data.detail;
        }
      }
      toast.error(`Ошибка: ${errorMsg}`, { duration: 6000 });
    } finally {
      setChoosing(false);
    }
  }

  // ── Loading ──
  if (introStatus.loading) {
    return (
      <Layout>
        <div className="max-w-3xl mx-auto pt-32 pb-16 px-4 text-center">
          <Sparkles className="w-10 h-10 text-primary mx-auto animate-spin-slow opacity-60" />
          <p className="text-sm text-muted mt-6 uppercase tracking-widest">
            {dict.classPage?.locked?.checking || "Проверяю твой путь..."}
          </p>
        </div>
      </Layout>
    );
  }

  // ── Skill Tree ──
  const classDict = dict.classPage?.classes || {};
  const nodes = TREE.map((n) => ({
    ...n,
    // Если класс УЖЕ выбран — открываем все ветви для свободной смены.
    locked: hasClass ? false : n.locked,
    isCurrent: n.id === currentClass,
    name: classDict[n.id]?.name || n.id,
    focus: classDict[n.id]?.focus || "База",
    desc: classDict[n.id]?.desc || "Описание класса",
    crest: classDict[n.id]?.crest || "⚔️",
    Icon: ICONS[n.id] || Code,
  }));
  const root = nodes.find((n) => n.tier === 0);
  const branches = nodes.filter((n) => n.tier === 1);

  // CTA меняется в зависимости от состояния
  const baseCta = dict.classPage?.cta || "Принять клятву";
  const ctaFor = (node) => {
    if (node.isCurrent) return "✓ Текущий класс";
    if (hasClass) return "Сменить на этот класс";
    return baseCta;
  };

  return (
    <Layout>
      <div className="max-w-6xl mx-auto pt-24 pb-16 px-4">
        
        {/* Баннер рекомендации, если вводный курс не пройден */}
        {introStatus.locked && (
          <div className="bg-panel border border-accent/50 rounded-2xl p-6 mb-12 max-w-3xl mx-auto flex items-start gap-4 shadow-[0_0_20px_rgba(var(--accent-rgb),0.15)]">
            <div className="bg-accent/20 p-3 rounded-full text-accent">
              <Sparkles size={24} />
            </div>
            <div>
              <h3 className="text-lg font-bold text-text mb-2">Рекомендация Академии</h3>
              <p className="text-sm text-muted">
                Мы видим, что ты еще не завершил Вводный курс. Ты можешь просмотреть древо классов и выбрать свой путь, но для полного понимания механик игры настоятельно рекомендуем сначала пройти базу!
              </p>
            </div>
          </div>
        )}

        {/* Header */}
        <header className="mb-12 text-center max-w-3xl mx-auto border-b border-border pb-10">
          <p className="text-xs uppercase tracking-widest text-primary mb-4 font-bold">
            {hasClass ? "Смена пути" : (dict.classPage?.alignment || "Выравнивание")}
          </p>
          <h1 className="text-4xl md:text-6xl font-display font-bold text-text mb-6">
            {hasClass ? "Сменить класс" : "Древо Классов"}
          </h1>
          <p className="text-lg text-muted leading-relaxed">
            {hasClass
              ? "Перевыбери свой путь. Все ветви открыты — выбирай, во что хочешь развиваться дальше."
              : "Начни с базовой магии Python. Ветви Django и DevOps откроются после освоения корня."}
          </p>
        </header>

        {/* Skill Tree Container */}
        <div className="relative flex flex-col items-center max-w-5xl mx-auto">
          {/* ── Root Node: Python ── */}
          <motion.div
            initial={{ opacity: 0, y: -20, scale: 0.94 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.6, ease: "easeOut" }}
            className="relative z-20"
          >
            <SkillNode
              node={root}
              onSelect={() => choose(root.id)}
              choosing={choosing}
              cta={ctaFor(root)}
            />
          </motion.div>

          {/* ── SVG Connector Lines ── */}
          <div className="relative w-full max-w-3xl h-24 pointer-events-none">
            <svg
              className="absolute inset-0 w-full h-full"
              viewBox="0 0 800 100"
              preserveAspectRatio="none"
              aria-hidden="true"
            >
              <defs>
                <linearGradient id="skillLineGrad" x1="0" x2="0" y1="0" y2="1">
                  <stop offset="0%" stopColor="var(--primary)" stopOpacity="0.9" />
                  <stop offset="100%" stopColor="var(--primary)" stopOpacity="0.15" />
                </linearGradient>
              </defs>
              <motion.path
                d="M 400 0 Q 400 50 180 100"
                fill="none"
                stroke="url(#skillLineGrad)"
                strokeWidth="2.5"
                strokeDasharray="6 6"
                initial={{ pathLength: 0, opacity: 0 }}
                animate={{ pathLength: 1, opacity: 1 }}
                transition={{ duration: 1.1, delay: 0.5, ease: "easeOut" }}
              />
              <motion.path
                d="M 400 0 Q 400 50 620 100"
                fill="none"
                stroke="url(#skillLineGrad)"
                strokeWidth="2.5"
                strokeDasharray="6 6"
                initial={{ pathLength: 0, opacity: 0 }}
                animate={{ pathLength: 1, opacity: 1 }}
                transition={{ duration: 1.1, delay: 0.7, ease: "easeOut" }}
              />
            </svg>
          </div>

          {/* ── Branch Nodes: Django + DevOps ── */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 w-full max-w-3xl">
            {branches.map((node, i) => (
              <motion.div
                key={node.id}
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.95 + i * 0.15, ease: "easeOut" }}
                className="flex justify-center"
              >
                <SkillNode
                  node={node}
                  onSelect={() => choose(node.id)}
                  choosing={choosing}
                  cta={ctaFor(node)}
                />
              </motion.div>
            ))}
          </div>

          {/* Footer hint */}
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 1.4, duration: 0.5 }}
            className="text-xs text-muted text-center mt-10 italic max-w-md"
          >
            {hasClass
              ? "Сменить класс можно в любой момент. Прогресс по миссиям сохраняется."
              : "Ветви Django и DevOps откроются после прохождения базовой магии Python."}
          </motion.p>
        </div>
      </div>

      <ConfirmModal data={confirmData} onClose={() => setConfirmData(null)} />
    </Layout>
  );
}

function SkillNode({ node, onSelect, choosing, cta }) {
  const Icon = node.Icon;
  const isLocked = node.locked;
  const isCurrent = node.isCurrent;

  const handleKey = (e) => {
    if (isLocked) return;
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onSelect?.();
    }
  };

  return (
    <motion.div
      whileHover={isLocked ? {} : { scale: 1.04, y: -6 }}
      whileTap={isLocked ? {} : { scale: 0.98 }}
      transition={{ type: "spring", stiffness: 300, damping: 20 }}
      onClick={isLocked ? undefined : onSelect}
      role={isLocked ? undefined : "button"}
      tabIndex={isLocked ? -1 : 0}
      onKeyDown={handleKey}
      aria-disabled={isLocked}
      aria-label={
        isLocked
          ? `${node.name} — заблокировано`
          : isCurrent
          ? `${node.name} — текущий класс`
          : `Выбрать ${node.name}`
      }
      className={`group relative w-full max-w-[300px] rounded-[2rem] border-2 p-6 overflow-hidden transition-all duration-500 outline-none focus-visible:ring-2 focus-visible:ring-primary
        ${
          isLocked
            ? "border-border bg-panel/60 cursor-not-allowed opacity-60"
            : isCurrent
            ? "border-accent bg-surface cursor-pointer shadow-[0_0_40px_var(--accent)] hover:border-accent"
            : "border-primary/60 bg-surface cursor-pointer shadow-[0_0_30px_var(--primary-selection)] hover:border-primary"
        }`}
    >
      {isCurrent && (
        <div className="absolute top-3 right-3 z-20 flex items-center gap-1 bg-accent/20 border border-accent/60 text-accent text-[10px] font-bold uppercase tracking-widest px-2 py-1 rounded-full">
          <Check size={10} /> Текущий
        </div>
      )}
      {!isLocked && (
        <div
          className={`absolute inset-0 bg-gradient-to-b ${
            isCurrent ? "from-accent/15" : "from-primary/15"
          } via-transparent to-transparent pointer-events-none`}
        />
      )}

      <div className="relative z-10">
        <div className="flex items-center justify-between mb-5">
          <div
            className={`w-14 h-14 rounded-2xl flex items-center justify-center text-3xl border shadow-inner
            ${
              isLocked
                ? "bg-panel border-border"
                : isCurrent
                ? "bg-accent/10 border-accent/40 group-hover:scale-110 group-hover:rotate-3 transition-transform duration-500"
                : "bg-primary/10 border-primary/40 group-hover:scale-110 group-hover:rotate-3 transition-transform duration-500"
            }`}
          >
            <span className="drop-shadow-md">{node.crest}</span>
          </div>
          <div
            className={`w-10 h-10 rounded-full flex items-center justify-center transition-all duration-300
            ${
              isLocked
                ? "bg-panel text-muted border border-border"
                : isCurrent
                ? "bg-accent/15 text-accent border border-accent/40"
                : "bg-primary/15 text-primary group-hover:bg-primary group-hover:text-white group-hover:shadow-[0_0_15px_var(--primary)]"
            }`}
          >
            {isLocked ? <Lock size={16} /> : <Icon size={18} />}
          </div>
        </div>

        <p
          className={`text-[10px] font-bold uppercase tracking-widest mb-1
          ${isLocked ? "text-muted" : isCurrent ? "text-accent" : "text-primary"}`}
        >
          {isLocked
            ? "Заблокировано"
            : isCurrent
            ? "Выбранный путь"
            : node.tier === 0
            ? "Стартовая ветвь"
            : "Доступная ветвь"}
        </p>
        <h3 className="text-xl font-display font-bold text-text mb-2">{node.name}</h3>
        <p className="text-[10px] font-bold uppercase tracking-widest text-accent mb-3">
          {node.focus}
        </p>
        <p className="text-sm text-muted leading-relaxed mb-5">{node.desc}</p>

        {isLocked ? (
          <div className="flex items-center gap-2 text-xs text-muted">
            <Lock size={12} />
            <span className="uppercase tracking-wider">Требуется база Python</span>
          </div>
        ) : isCurrent ? (
          <div className="w-full text-center bg-accent/20 text-accent border border-accent/60 rounded-xl py-3 font-semibold cursor-default">
            {cta}
          </div>
        ) : (
          <div
            className={`w-full text-center bg-primary text-white border border-primary-dk rounded-xl py-3 font-semibold transition-shadow
              ${choosing ? "opacity-60" : "hover:shadow-[0_0_20px_var(--primary-selection)]"}`}
          >
            {choosing ? "..." : cta}
          </div>
        )}
      </div>
    </motion.div>
  );
}