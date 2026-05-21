import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/router";
import { motion } from "framer-motion"; // <-- Добавили framer-motion
import Layout from "../components/Layout";
import Button from "../components/Button";
import { setPlayerClass, getPlayerClass, fetchIntroStatus } from "../lib/class";
import { Profile } from "../lib/api";
import { toast } from "sonner";
import { Code, ServerCog, Share2, Lock, Sparkles } from "lucide-react";
import { useDictionary } from "../lib/i18n";

// Maps frontend class id to backend ClassRole pk (see fixtures/class_roles.json)
const CLASS_ROLE_IDS = {
  python: 1,  // Маг Кода
  django: 2,  // Рыцарь Логики
  devops: 3,  // Друид Данных
};

const CLASS_ICONS = {
  django: ServerCog,
  python: Code,
  devops: Share2,
};

export default function ChooseClassPage() {
  const dict = useDictionary();
  const router = useRouter();

  const classes = useMemo(() => {
    return Object.entries(dict.classPage.classes).map(([id, data]) => ({
      id,
      ...data,
      icon: CLASS_ICONS[id] || Code,
    }));
  }, [dict.classPage.classes]);

  // ── Intro gate state ──
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
      // Fail-open: если бэкенд недоступен, не блокируем выбор.
      if (!data) {
        setIntroStatus({ loading: false, locked: false, data: null });
        return;
      }
      setIntroStatus({
        loading: false,
        locked: !data.class_unlocked,
        data,
      });
    });
    return () => {
      cancelled = true;
    };
  }, [router]);

  async function choose(id) {
    if (choosing) return;
    setChoosing(true);
    try {
      const classRoleId = CLASS_ROLE_IDS[id];
      if (classRoleId) {
        // Save to backend first
        await Profile.update({ class_role: classRoleId });
      }
      // Save to localStorage for quick local access
      setPlayerClass(id);
      toast.success(dict.classPage.toastSuccess, { duration: 3000 });
      router.push("/profile");
    } catch (err) {
      toast.error("Не удалось сохранить класс. Попробуй ещё раз.", { duration: 4000 });
    } finally {
      setChoosing(false);
    }
  }

  // ── Loading state ──
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

  // ── Locked state: intro course not completed ──
  if (introStatus.locked) {
    const info = introStatus.data?.intro_track;
    const prog = introStatus.data?.progress;
    const percent =
      prog && prog.total > 0 ? Math.round((prog.completed / prog.total) * 100) : 0;
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
                  }. Там ты освоишь основы, на которых строится магия каждого класса.`}
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

  return (
    <Layout>
      <div className="max-w-6xl mx-auto pt-24 pb-16 px-4 transition-colors duration-300">
        
        {/* ── Заголовок ── */}
        <header className="mb-16 text-center max-w-3xl mx-auto border-b border-border pb-10">
          <p className="text-xs uppercase tracking-widest text-primary mb-4 font-bold">
            {dict.classPage.alignment}
          </p>
          <h1 className="text-4xl md:text-6xl font-display font-bold text-text mb-6">
            {dict.classPage.heading}
          </h1>
          <p className="text-lg text-muted leading-relaxed">
            {dict.classPage.subheading}
          </p>
        </header>

        {/* ── Карточки классов ── */}
        <div className="grid lg:grid-cols-3 gap-8">
          {classes.map((c) => {
            const Icon = c.icon;
            return (
              <motion.div
                key={c.id}
                whileHover={{ scale: 1.05, y: -10 }} // Эффект левитации
                whileTap={{ scale: 0.98 }}
                transition={{ type: "spring", stiffness: 300, damping: 20 }}
                onClick={() => choose(c.id)}
                className="group relative flex flex-col p-8 rounded-[2.5rem] border border-border bg-surface hover:border-primary transition-all duration-500 hover:shadow-[0_0_40px_var(--primary-selection)] overflow-hidden cursor-pointer"
              >
                {/* Текстура пергамента на фоне */}
                <div className="absolute inset-0 pointer-events-none opacity-[0.12] dark:opacity-[0.15] mix-blend-multiply dark:mix-blend-overlay rounded-[inherit]">
                  <svg className="w-full h-full">
                    <filter id={`paper-noise-${c.id}`}>
                      <feTurbulence type="fractalNoise" baseFrequency="0.8" numOctaves="4" stitchTiles="stitch" />
                    </filter>
                    <rect width="100%" height="100%" filter={`url(#paper-noise-${c.id})`} />
                  </svg>
                </div>

                {/* Верхний градиентный блик при наведении */}
                <div className="absolute top-0 left-0 w-full h-40 bg-gradient-to-b from-primary/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-700" />

                <div className="relative z-10 flex flex-col h-full pointer-events-none">
                  {/* Иконка и Герб */}
                  <div className="flex items-center justify-between mb-8">
                    <div className="w-16 h-16 rounded-2xl bg-panel border border-border flex items-center justify-center text-4xl shadow-inner group-hover:scale-110 group-hover:rotate-6 group-hover:border-primary/50 transition-all duration-500">
                      <span className="drop-shadow-md">{c.crest}</span>
                    </div>
                    <div className="w-12 h-12 rounded-full bg-primary/10 text-primary flex items-center justify-center opacity-50 group-hover:opacity-100 group-hover:bg-primary group-hover:text-white transition-all duration-500 group-hover:shadow-[0_0_15px_var(--primary)]">
                      <Icon size={24} />
                    </div>
                  </div>

                  {/* Текст и описание */}
                  <div className="mb-8 flex-1">
                    <h3 className="text-2xl font-display font-bold text-text mb-2 group-hover:text-primary transition-colors duration-300">
                      {c.name}
                    </h3>
                    <p className="text-[10px] font-bold uppercase tracking-widest text-accent mb-4">
                      {c.focus}
                    </p>
                    <p className="text-sm text-muted leading-relaxed">
                      {c.desc}
                    </p>
                  </div>

                  {/* Кнопка принятия клятвы (Визуальная, т.к. кликабельна вся карточка) */}
                  <Button 
                    className="w-full bg-panel text-text border border-border group-hover:bg-primary group-hover:text-white group-hover:border-primary-dk transition-all duration-300 shadow-none group-hover:shadow-[0_0_20px_var(--primary-selection)] pointer-events-none" 
                  >
                    {dict.classPage.cta}
                  </Button>
                </div>
              </motion.div>
            );
          })}
        </div>
      </div>
    </Layout>
  );
}