import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import { motion } from "framer-motion";
import Layout from "../components/Layout";
import Button from "../components/Button";
import { setPlayerClass, getPlayerClass, fetchIntroStatus } from "../lib/class";
import { Profile } from "../lib/api";
import { toast } from "sonner";
import { Code, ServerCog, Share2, Lock, Sparkles } from "lucide-react";
import { useDictionary } from "../lib/i18n";

// Frontend id → backend ClassRole pk (must match fixtures/class_roles.json)
const CLASS_ROLE_IDS = { python: 1, django: 2, devops: 3 };

const ICONS = { python: Code, django: ServerCog, devops: Share2 };

// Skill-tree topology. tier=0 is root (Python). Branches require Python first.
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

  useEffect(() => {
    const chosen = getPlayerClass();
    if (chosen) {
      router.push("/worlds");
      return;
    }
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
  }, [router]);

  async function choose(id) {
    const node = TREE.find((n) => n.id === id);
    if (!node || node.locked || choosing) return;
    setChoosing(true);
    try {
      const classRoleId = CLASS_ROLE_IDS[id];
      if (classRoleId) {
        await Profile.update({ class_role: classRoleId });
      }
      setPlayerClass(id);
      toast.success(dict.classPage.toastSuccess, { duration: 3000 });
      router.push("/profile");
    } catch (e) {
      toast.error("Не удалось сохранить класс. Попробуй ещё раз.", { duration: 4000 });
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

  // ── Locked (intro not finished) ──
  if (introStatus.locked) {
    const info = introStatus.data?.intro_track;
    const prog = introStatus.data?.progress;
    const percent = prog && prog.total > 0 ? Math.round((prog.completed / prog.total) * 100) : 0;
    return (
      <Layout>
        <div className="max-w-3xl mx-auto pt-24 pb-16 px-4">
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: "easeOut" }}
            className="text-center border border-border bg-surface rounded-[2.5rem] p-10 md:p-14 relative overflow-hidden"
          >
            <div className="absolute inset-0 bg-gradient-to-b from-primary/10 via-transparent to-transparent pointer-events-none" />
            <div className="relative z-10">
              <div className="w-20 h-20 mx-auto rounded-full bg-panel border border-border flex items-center justify-center mb-6 shadow-inner">
                <Lock size={32} className="text-muted" />
              </div>
              <p className="text-xs uppercase tracking-widest text-primary mb-4 font-bold">
                {dict.classPage?.locked?.kicker || "Класс пока заблокирован"}
              </p>
              <h1 className="text-4xl md:text-5xl font-display font-bold text-text mb-6">
                {dict.classPage?.locked?.heading || "Сначала пройди Вводный Курс"}
              </h1>
              <p className="text-lg text-muted leading-relaxed mb-8">
                {dict.classPage?.locked?.subheading ||
                  `Прежде чем выбрать своё призвание, заверши вводный трек${
                    info?.title ? ` «${info.title}»` : ""
                  }.`}
              </p>
              {prog && (
                <div className="mb-8 max-w-md mx-auto">
                  <div className="flex justify-between text-xs text-muted mb-2 uppercase tracking-widest">
                    <span>{dict.classPage?.locked?.progressLabel || "Прогресс"}</span>
                    <span>
                      {prog.completed} / {prog.total}
                    </span>
                  </div>
                  <div className="h-2 rounded-full bg-panel overflow-hidden border border-border">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${percent}%` }}
                      transition={{ duration: 0.9, ease: "easeOut" }}
                      className="h-full bg-gradient-to-r from-primary to-accent"
                    />
                  </div>
                </div>
              )}
              <Button
                onClick={() => router.push("/worlds")}
                className="bg-primary text-white hover:bg-primary-dk shadow-[0_0_20px_var(--primary-selection)]"
              >
                {dict.classPage?.locked?.cta || "К вводному курсу"}
              </Button>
            </div>
          </motion.div>
        </div>
      </Layout>
    );
  }

  // ── Skill Tree ──
  const classDict = dict.classPage.classes;
  const nodes = TREE.map((n) => ({
    ...n,
    name: classDict[n.id]?.name,
    focus: classDict[n.id]?.focus,
    desc: classDict[n.id]?.desc,
    crest: classDict[n.id]?.crest,
    Icon: ICONS[n.id] || Code,
  }));
  const root = nodes.find((n) => n.tier === 0);
  const branches = nodes.filter((n) => n.tier === 1);

  return (
    <Layout>
      <div className="max-w-6xl mx-auto pt-24 pb-16 px-4">
        {/* Header */}
        <header className="mb-12 text-center max-w-3xl mx-auto border-b border-border pb-10">
          <p className="text-xs uppercase tracking-widest text-primary mb-4 font-bold">
            {dict.classPage.alignment}
          </p>
          <h1 className="text-4xl md:text-6xl font-display font-bold text-text mb-6">
            Древо Классов
          </h1>
          <p className="text-lg text-muted leading-relaxed">
            Начни с базовой магии Python. Ветви Django и DevOps откроются после освоения корня.
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
              cta={dict.classPage.cta}
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
                <SkillNode node={node} cta={dict.classPage.cta} />
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
            Ветви Django и DevOps откроются после прохождения базовой магии Python.
          </motion.p>
        </div>
      </div>
    </Layout>
  );
}

function SkillNode({ node, onSelect, choosing, cta }) {
  const Icon = node.Icon;
  const isLocked = node.locked;

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
      aria-label={isLocked ? `${node.name} — заблокировано` : `Выбрать ${node.name}`}
      className={`group relative w-full max-w-[300px] rounded-[2rem] border-2 p-6 overflow-hidden transition-all duration-500 outline-none focus-visible:ring-2 focus-visible:ring-primary
        ${
          isLocked
            ? "border-border bg-panel/60 cursor-not-allowed opacity-60"
            : "border-primary/60 bg-surface cursor-pointer shadow-[0_0_30px_var(--primary-selection)] hover:border-primary"
        }`}
    >
      {!isLocked && (
        <div className="absolute inset-0 bg-gradient-to-b from-primary/15 via-transparent to-transparent pointer-events-none" />
      )}

      <div className="relative z-10">
        <div className="flex items-center justify-between mb-5">
          <div
            className={`w-14 h-14 rounded-2xl flex items-center justify-center text-3xl border shadow-inner
            ${
              isLocked
                ? "bg-panel border-border"
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
                : "bg-primary/15 text-primary group-hover:bg-primary group-hover:text-white group-hover:shadow-[0_0_15px_var(--primary)]"
            }`}
          >
            {isLocked ? <Lock size={16} /> : <Icon size={18} />}
          </div>
        </div>

        <p
          className={`text-[10px] font-bold uppercase tracking-widest mb-1
          ${isLocked ? "text-muted" : "text-primary"}`}
        >
          {isLocked ? "Заблокировано" : "Стартовая ветвь"}
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
