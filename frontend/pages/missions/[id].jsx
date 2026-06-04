import Layout from "../../components/Layout";
import Button from "../../components/Button";
import MissionStepper from "../../components/MissionStepper";
import CodeRunnerPanel from "../../components/CodeRunnerPanel";
import CodemancerStage from "../../components/CodemancerStage";
import { useRouter } from "next/router";
import { toast } from "sonner";
import {
  Missions,
  TaskProgressAPI,
  Profile, // Импортируем Profile для работы с инвентарем
} from "../../lib/api";
import { useEffect, useMemo, useState } from "react";
import { Sword, Sparkles, Code2, BookOpen, Lock, ChevronRight, ScrollText } from "lucide-react";
import logger from "../../lib/logger";
import { useI18n } from "../../lib/i18n";

export default function MissionDetail() {
  const router = useRouter();
  const { id } = router.query;
  const { language, t } = useI18n();
  const [mission, setMission] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [activeTaskId, setActiveTaskId] = useState(null);
  const [taskProgress, setTaskProgress] = useState({});
  const [codeDrafts, setCodeDrafts] = useState({});
  const [quizAnswers, setQuizAnswers] = useState({});
  const [savingTaskId, setSavingTaskId] = useState(null);

  // --- СТЕЙТ ДЛЯ ИНВЕНТАРЯ ---
  const [inventory, setInventory] = useState({
    ai_summons: 0,
    hint_scrolls: 0,
    skeleton_scrolls: 0,
  });

  // Уровень игрока для HUD игровой сцены (Codemancer)
  const [playerLevel, setPlayerLevel] = useState(1);

  // Боевая фаза сцены, завязанная на действия игрока в задаче:
  // idle | casting (код выполняется) | victory (тест пройден) | defeat (ошибка).
  // tick перезапускает one-shot анимации (снаряд, вспышка) при каждом событии.
  const [stage, setStage] = useState({ phase: "idle", tick: 0 });

  const activeTask = useMemo(() => {
    return tasks.find((t) => t.id === activeTaskId) || tasks[0] || null;
  }, [tasks, activeTaskId]);

  // Загрузка данных миссии и инвентаря пользователя
  useEffect(() => {
    if (!id) return;
    let active = true;

    // 1. Загружаем данные миссии
    Missions.get(id)
      .then((data) => {
        if (!active) return;
        setMission(data);
        if (data.tasks && data.tasks.length > 0) {
          setTasks(data.tasks);
          setActiveTaskId(data.tasks[0].id);
        }
      })
      .catch(() => {
        toast.error(t("missionPage.toasts.loadFail"));
      });

    // 2. Загружаем прогресс задач
    TaskProgressAPI.list(id)
      .then((progressList) => {
        if (!active) return;
        const mapping = {};
        const drafts = {};
        progressList.forEach((p) => {
          const tid = p.task_id ?? p.task;
          mapping[tid] = p;
          if (p.answer && p.answer.code) {
            drafts[tid] = p.answer.code;
          }
        });
        setTaskProgress(mapping);
        setCodeDrafts(drafts);
      })
      .catch(() => {});

    // 3. Загружаем профиль для получения актуального инвентаря.
    // Новый ProfileMeView возвращает плоский payload — поля ai_summons/hint_scrolls/
    // skeleton_scrolls лежат прямо в корне объекта. Старую вложенную форму
    // (data.profile.xxx) поддерживаем как fallback для /auth/me/.
    Profile.me()
      .then((userDoc) => {
        if (!active || !userDoc) return;
        const p = userDoc.profile ?? userDoc;
        setInventory({
          ai_summons: p.ai_summons ?? 0,
          hint_scrolls: p.hint_scrolls ?? 0,
          skeleton_scrolls: p.skeleton_scrolls ?? 0,
        });
        setPlayerLevel(p.level ?? 1);
      })
      .catch((err) => {
        logger.error("Не удалось загрузить инвентарь игрока:", err);
      });

    return () => {
      active = false;
    };
    // MID-06: при смене языка миссия перезагружается с правильными title_ru/title_en
  }, [id, language]);

  // Сцена сама возвращается в покой после реакции на запуск кода.
  useEffect(() => {
    if (stage.phase === "idle") return;
    const ms =
      stage.phase === "casting" ? 20000 : stage.phase === "victory" ? 1100 : 800;
    const timer = setTimeout(() => setStage((s) => ({ ...s, phase: "idle" })), ms);
    return () => clearTimeout(timer);
  }, [stage.phase, stage.tick]);

  // CodeRunnerPanel сообщает фазу запуска кода → герой колдует / бьёт голема /
  // отшатывается. Это и есть интерактивность, завязанная на выполнение задания.
  const handleRunState = (state) => {
    const phase =
      state === "running" ? "casting" : state === "success" ? "victory" : "defeat";
    setStage((s) => ({ phase, tick: s.tick + 1 }));
  };

  // Коллбэк для обновления инвентаря из CodeRunnerPanel
  const handleInventoryUpdate = (itemType, remainingCount) => {
    setInventory((prev) => ({
      ...prev,
      [itemType]: remainingCount,
    }));
  };

  const codeValue = useMemo(() => {
    if (!activeTaskId) return "";
    if (codeDrafts[activeTaskId] !== undefined) {
      return codeDrafts[activeTaskId];
    }
    return activeTask?.data?.starter || "";
  }, [codeDrafts, activeTaskId, activeTask]);

  // Called by CodeRunnerPanel when the streaming runner returns exit code 0.
  // Persists the code draft and marks the task as completed.
  const handleTestPassed = async (payload) => {
    if (!activeTask) return;
    const codeToRun =
      codeDrafts[activeTask.id] ?? activeTask.data?.starter ?? payload?.code ?? "";
    toast.success(t("missionPage.toasts.passed"));
    await handleCompleteTask(activeTask.id, { code: codeToRun }, 100);
  };

  const handleCompleteTask = async (taskId, answerData = {}, score = 0) => {
    setSavingTaskId(taskId);
    try {
      const updatedProgress = await TaskProgressAPI.submit(taskId, {
        status: "completed",
        score: score,
        answer: answerData,
      });

      setTaskProgress((prev) => ({
        ...prev,
        [taskId]: updatedProgress,
      }));

      toast.success(t("missionPage.toasts.stepSaved"));

      // Автоматический переход на следующий шаг
      const currentIndex = tasks.findIndex((t) => t.id === taskId);
      if (currentIndex !== -1 && currentIndex < tasks.length - 1) {
        setActiveTaskId(tasks[currentIndex + 1].id);
      } else {
        // Если это была последняя задача — завершаем миссию и обрабатываем награды
        try {
          const result = await Missions.complete(id);
          // CRIT-03: backend честно шлёт leveled_up/xp_added/new_level
          if (result?.xp_added > 0) {
            toast.success(
              t("missionPage.toasts.questDoneXp").replace("{xp}", result.xp_added),
              { duration: 4000 }
            );
          } else {
            toast.success(t("missionPage.toasts.questDone"));
          }
          if (result?.leveled_up) {
            // Двойной toast: общая победа + level-up отдельно
            setTimeout(() => {
              toast.success(
                t("missionPage.toasts.levelUp").replace("{level}", result.new_level),
                { duration: 6000 }
              );
            }, 800);
          }

          // TC-RANK-01: refetch profile to show updated rank on level-up
          // and update inventory with any rewards granted
          try {
            const profileData = await Profile.me();
            if (profileData) {
              const p = profileData.profile ?? profileData;
              setInventory({
                ai_summons: p.ai_summons ?? 0,
                hint_scrolls: p.hint_scrolls ?? 0,
                skeleton_scrolls: p.skeleton_scrolls ?? 0,
              });
              setPlayerLevel(p.level ?? 1);
            }
          } catch (profileErr) {
            logger.error("Failed to refetch profile after mission complete:", profileErr);
          }
        } catch (err) {
          logger.error("Mission.complete failed:", err);
        }
      }
    } catch (e) {
      toast.error(t("missionPage.toasts.saveFail"));
    } finally {
      setSavingTaskId(false);
    }
  };

  const handleQuizSubmit = (taskId) => {
    const userAnswer = quizAnswers[taskId];
    const currentTask = tasks.find((t) => t.id === taskId);
    if (!currentTask) return;

    // Поддерживаем 2 формата фикстуры:
    // 1) data.correct_answer = "break"
    // 2) data.options = [{ value: "break", isCorrect: true }, ...]
    let correctAnswer = currentTask.data?.correct_answer;
    if (!correctAnswer && Array.isArray(currentTask.data?.options)) {
      const correctOpt = currentTask.data.options.find((o) => o && o.isCorrect);
      correctAnswer = correctOpt?.value ?? correctOpt?.label;
    }
    if (String(userAnswer).trim().toLowerCase() === String(correctAnswer).trim().toLowerCase()) {
      handleCompleteTask(taskId, { selected: userAnswer }, 100);
    } else {
      toast.error(t("missionPage.quizWrong"));
    }
  };

  if (!mission) {
    return (
      <Layout fullBleed hideFooter>
        <div className="h-screen pt-24 bg-bg dark:bg-[#0f0f11] flex items-center justify-center font-mono">
          <div className="text-center space-y-4">
            <div className="w-12 h-12 border-4 border-t-[#d4a24c] border-[#c9b48a] dark:border-[#3a2818] rounded-full animate-spin mx-auto"></div>
            <p className="text-accent dark:text-[#d4a24c] tracking-widest text-sm uppercase">{t("missionPage.loading")}</p>
          </div>
        </div>
      </Layout>
    );
  }

  // Миссия заблокирована — prerequisites не выполнены
  if (mission.available === false) {
    const prereqs = mission.prerequisites || [];
    return (
      <Layout fullBleed hideFooter>
        <div className="h-screen pt-24 bg-bg dark:bg-[#0f0f11] flex items-center justify-center px-4">
          <div className="max-w-md w-full text-center space-y-6">
            <div className="w-20 h-20 rounded-full bg-surface dark:bg-[#1a1a20] border-2 border-border dark:border-[#333] flex items-center justify-center mx-auto">
              <Lock size={36} className="text-faint dark:text-[#555]" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-text dark:text-white tracking-wide mb-2">
                {t("missionPage.locked.title")}
              </h1>
              <p className="text-muted dark:text-gray-400 text-sm leading-relaxed">
                {t("missionPage.locked.body").replace(
                  "{title}",
                  (language === "en"
                    ? mission.title_en || mission.title_ru
                    : mission.title_ru || mission.title_en) ||
                    mission.title ||
                    ""
                )}
              </p>
            </div>
            {prereqs.length > 0 && (
              <div className="bg-panel dark:bg-[#141418] border border-border dark:border-[#222] rounded-xl p-4 text-left space-y-2">
                <p className="text-xs font-mono uppercase tracking-widest text-muted dark:text-gray-500 mb-3">
                  {t("missionPage.locked.prereqs")}
                </p>
                {prereqs.map((pre) => (
                  <div key={pre.id} className="flex items-center gap-2 text-sm text-text dark:text-gray-300">
                    <ChevronRight size={14} className="text-purple-400 shrink-0" />
                    <span>{pre.title}</span>
                  </div>
                ))}
              </div>
            )}
            <Button
              variant="secondary"
              onClick={() => router.push("/worlds")}
              className="w-full justify-center"
            >
              {t("missionPage.locked.back")}
            </Button>
          </div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout fullBleed hideFooter>
      <div className="h-screen pt-24 bg-bg dark:bg-[#0f0f11] text-text dark:text-gray-200 font-sans flex flex-col">
        {/* Квест-шапка в RPG-стиле: deep-wood band + scroll icon + Melodrama.
            Светлая тема — чистая surface-полоса; тёмная — глубокое дерево. */}
        <header className="border-b border-border dark:border-[#5c3a21]/40 px-4 sm:px-8 py-4 flex items-center justify-between gap-3 select-none shadow-md bg-surface dark:bg-gradient-to-r dark:from-[#2b1d11] dark:via-[#3a2818] dark:to-[#2b1d11]">
          <div className="flex items-center gap-3 sm:gap-4 min-w-0">
            <div className="shrink-0 p-2.5 bg-primary/10 dark:bg-[#8b5a2b]/25 border border-primary/20 dark:border-[#d4a24c]/60 rounded-xl text-primary dark:text-[#fde68a] shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]">
              <ScrollText size={22} />
            </div>
            <div className="min-w-0">
              <h1 className="font-display text-xl sm:text-2xl font-bold text-text dark:text-[#fde68a] tracking-wide truncate dark:drop-shadow-[0_1px_0_rgba(0,0,0,0.4)]">
                {(language === "en"
                  ? mission.title_en || mission.title_ru
                  : mission.title_ru || mission.title_en) ||
                  mission.title}
              </h1>
              <p className="text-xs text-accent dark:text-[#d4a24c] font-mono mt-0.5 uppercase tracking-wider">
                {t("missionPage.rewardLabel")}: <span className="text-text dark:text-[#fde68a] font-bold">{mission.xp_reward}</span> {t("missionPage.xpGained")}
              </p>
            </div>
          </div>
          <Button variant="secondary" size="sm" className="shrink-0" onClick={() => router.push("/worlds")}>
            {t("missionPage.backToMap")}
          </Button>
        </header>

        {/* Игровая сцена Codemancer: пиксель-арт + HUD (HP/MP/Level).
            MP завязана на ai_summons (мана для AI-призывов), HP — флейвор. */}
        <CodemancerStage
          level={playerLevel}
          hpPct={100}
          mpPct={Math.min(100, (inventory.ai_summons || 0) * 20)}
          phase={stage.phase}
          tick={stage.tick}
        />

        {/* Основной контент */}
        <section className="flex-1 flex flex-col xl:flex-row min-h-0 overflow-auto xl:overflow-hidden">
          {/* Левая панель (Quest Scrolls) — пергаментный фон.
              Текстура: base parchment color + 3 radial overlays (имитируют
              пятна и потёртости) + лёгкое sepia-tint поверх. Никаких
              файлов-текстур — чистый CSS, переживёт любую сборку. */}
          <div
            className="w-full xl:w-[320px] xl:flex-shrink-0 border-r-4 border-[#5c3a21]/60 flex flex-col select-none shadow-2xl z-10 relative"
            style={{
              backgroundColor: "#d4ad75",
              backgroundImage:
                "radial-gradient(circle at 15% 20%, rgba(60,30,10,0.18), transparent 35%)," +
                "radial-gradient(circle at 85% 70%, rgba(40,20,10,0.16), transparent 40%)," +
                "radial-gradient(circle at 50% 95%, rgba(80,40,15,0.10), transparent 50%)," +
                "linear-gradient(180deg, #dcb98a 0%, #d4ad75 50%, #c39858 100%)",
            }}
          >
            {/* Череп-тотем со стола мага — выцветший водяной знак (из мокапа
                Codemancer). Лежит позади контента, читаемость не трогает. */}
            <div
              className="pointer-events-none absolute inset-x-0 bottom-24 z-0 flex justify-center opacity-[0.07]"
              aria-hidden="true"
            >
              <svg viewBox="0 0 200 200" className="w-44 h-44 text-[#2a1810]">
                <path d="M100 30c-38 0-66 28-66 64 0 22 12 36 22 46v22c0 6 4 10 10 10h12v-14h14v14h16v-14h14v14h12c6 0 10-4 10-10v-22c10-10 22-24 22-46 0-36-28-64-66-64z" fill="currentColor" />
                <ellipse cx="74" cy="110" rx="18" ry="22" fill="#dcb98a" />
                <ellipse cx="126" cy="110" rx="18" ry="22" fill="#dcb98a" />
                <path d="M100 130l-10 18h20z" fill="#dcb98a" />
                <path d="M86 160h6v10h-6zM100 160h6v10h-6zM114 160h6v10h-6z" fill="#dcb98a" />
              </svg>
            </div>

            {/* Заголовок-баннер */}
            <div className="relative z-10 px-6 py-4 border-b-2 border-[#5c3a21]/40 bg-gradient-to-r from-[#3a2818]/95 via-[#5c3a21]/90 to-[#3a2818]/95 flex items-center gap-2">
              <ScrollText size={16} className="text-[#fde68a]" />
              <p className="font-display text-sm font-bold tracking-widest text-[#fde68a] uppercase">
                {t("missionPage.questLog")}
              </p>
              {/* Свеча на столе мага — мягко мерцающее пламя (чистый SVG + Tailwind) */}
              <svg width="14" height="24" viewBox="0 0 14 24" className="ml-auto shrink-0" aria-hidden="true">
                <ellipse cx="7" cy="22" rx="4.5" ry="1.4" fill="#1c120a" opacity="0.5" />
                <rect x="4.5" y="9" width="5" height="13" rx="1.2" fill="#f3e2c0" />
                <rect x="4.6" y="9" width="1.7" height="13" rx="0.8" fill="#ffffff" opacity="0.35" />
                <rect x="6.6" y="6" width="0.8" height="3" fill="#3e2723" />
                <g className="animate-flicker" style={{ transformOrigin: "7px 7px" }}>
                  <path d="M7 0c1.7 1.8 2.5 3.2 2.5 4.6A2.5 2.5 0 0 1 7 7.1 2.5 2.5 0 0 1 4.5 4.6C4.5 3.2 5.3 1.8 7 0Z" fill="#ffb338" />
                  <path d="M7 2c.9 1 1.3 2 1.3 2.8A1.3 1.3 0 0 1 7 6.1 1.3 1.3 0 0 1 5.7 4.8C5.7 4 6.1 3 7 2Z" fill="#fff3c4" />
                </g>
              </svg>
            </div>

            <div className="relative z-10 flex-1 overflow-y-auto p-4">
              <MissionStepper
                tasks={tasks}
                activeId={activeTaskId}
                progress={taskProgress}
                onSelect={(taskId) => {
                  setActiveTaskId(taskId);
                }}
                variant="parchment"
              />
            </div>

            {/* Статистика текущей ноды — на тёмной полосе под пергаментом */}
            <div className="relative z-10 p-4 border-t-2 border-[#5c3a21]/40 bg-gradient-to-r from-[#3a2818]/95 via-[#5c3a21]/90 to-[#3a2818]/95 font-mono text-xs text-[#d4a24c]">
              {activeTask && (
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span>{t("missionPage.stats.fileType")}</span>
                    <span className="text-[#fde68a] uppercase font-semibold">{activeTask.task_type}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>{t("missionPage.stats.timeEstimate")}</span>
                    <span className="text-[#fde68a]">{activeTask.estimated_minutes} {t("missionPage.stats.minutesShort")}</span>
                  </div>
                  {taskProgress[activeTask.id] && (
                    <div className="mt-2 pt-2 border-t border-[#5c3a21]/40 space-y-1">
                      <p>{t("missionPage.stats.status")} <span className="text-[#a3e635] font-bold">{t("missionPage.stats.done")}</span></p>
                      <p>{t("missionPage.stats.attempts")} {taskProgress[activeTask.id].attempts || 1}</p>
                      <p>{t("missionPage.stats.best")} <span className="text-[#fde68a] font-bold">{taskProgress[activeTask.id].best_score || 0}</span></p>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Центральная панель (Свиток инструкций) — parchment под стать левой панели */}
          <div
            className="w-full xl:w-[420px] xl:flex-shrink-0 flex flex-col border-r-4 border-[#5c3a21]/60 min-w-0 relative"
            style={{
              backgroundColor: "#dcb98a",
              backgroundImage:
                "radial-gradient(circle at 80% 15%, rgba(60,30,10,0.16), transparent 35%)," +
                "radial-gradient(circle at 20% 60%, rgba(40,20,10,0.14), transparent 40%)," +
                "radial-gradient(circle at 50% 95%, rgba(80,40,15,0.10), transparent 50%)," +
                "linear-gradient(180deg, #dcb98a 0%, #d4ad75 60%, #c39858 100%)",
              // Тень-сгиб «разворота книги» по левому краю страницы инструкций
              boxShadow: "inset 16px 0 30px -16px rgba(40,20,8,0.6)",
            }}
          >
            {/* Header-баннер: тёмное дерево, иконка типа, fantasy title */}
            <div className="px-6 py-4 border-b-2 border-[#5c3a21]/40 bg-gradient-to-r from-[#3a2818]/95 via-[#5c3a21]/90 to-[#3a2818]/95 flex items-center gap-2">
              {activeTask?.task_type === "code"
                ? <Code2 size={16} className="text-[#d4a24c]" />
                : <BookOpen size={16} className="text-[#a3e635]" />}
              <h2 className="min-w-0 flex-1 font-display text-base font-bold text-[#fde68a] tracking-wide truncate drop-shadow-[0_1px_0_rgba(0,0,0,0.4)]">
                {(language === "en"
                  ? activeTask?.title_en || activeTask?.title_ru
                  : activeTask?.title_ru || activeTask?.title_en) ||
                  activeTask?.title ||
                  t("missionPage.scrollTitleFallback")}
              </h2>
              {/* Свеча — пара со столом квест-лога; единый «огонёк мага» */}
              <svg width="14" height="24" viewBox="0 0 14 24" className="ml-auto shrink-0" aria-hidden="true">
                <ellipse cx="7" cy="22" rx="4.5" ry="1.4" fill="#1c120a" opacity="0.5" />
                <rect x="4.5" y="9" width="5" height="13" rx="1.2" fill="#f3e2c0" />
                <rect x="4.6" y="9" width="1.7" height="13" rx="0.8" fill="#ffffff" opacity="0.35" />
                <rect x="6.6" y="6" width="0.8" height="3" fill="#3e2723" />
                <g className="animate-flicker" style={{ transformOrigin: "7px 7px" }}>
                  <path d="M7 0c1.7 1.8 2.5 3.2 2.5 4.6A2.5 2.5 0 0 1 7 7.1 2.5 2.5 0 0 1 4.5 4.6C4.5 3.2 5.3 1.8 7 0Z" fill="#ffb338" />
                  <path d="M7 2c.9 1 1.3 2 1.3 2.8A1.3 1.3 0 0 1 7 6.1 1.3 1.3 0 0 1 5.7 4.8C5.7 4 6.1 3 7 2Z" fill="#fff3c4" />
                </g>
              </svg>
            </div>

            {/* Орнаментальный разделитель главы — перо + росчерк (чистый SVG) */}
            <div className="flex items-center gap-3 px-6 pt-4 pb-1 select-none" aria-hidden="true">
              <span className="h-px flex-1 bg-gradient-to-r from-transparent via-[#5c3a21]/40 to-[#5c3a21]/60" />
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" className="shrink-0 text-[#5c3a21]">
                <path d="M4 20c4.5-1 7-3.2 10-7.3 2.2-3 3.8-6.4 6-11.7-5.6 1.8-9 4-12 7.3C5 11 4.6 15 4 20Z" fill="currentColor" opacity="0.5" />
                <path d="M4.2 19.8 9 15" stroke="#3e2723" strokeWidth="1" strokeLinecap="round" opacity="0.7" />
                <circle cx="12.6" cy="10.8" r="0.9" fill="#8e1d1d" />
              </svg>
              <span className="h-px flex-1 bg-gradient-to-l from-transparent via-[#5c3a21]/40 to-[#5c3a21]/60" />
            </div>

            {/* Тело свитка: тёмно-коричневый текст на пергаменте.
                `prose-invert` снят — у нас светлый фон. Цвета через явные классы,
                чтобы prose не пытался применить ни тёмную, ни системную палитру. */}
            <div className="flex-1 overflow-y-auto p-6 prose max-w-none text-sm text-[#3e2723] leading-relaxed space-y-4
              prose-headings:font-display prose-headings:text-[#3e2723]
              prose-strong:text-[#3e2723]
              prose-code:bg-[#5c3a21]/15 prose-code:text-[#5c3a21] prose-code:px-1 prose-code:rounded
              prose-pre:bg-[#3a2818] prose-pre:text-[#fde68a]
              prose-a:text-[#8e1d1d] prose-li:marker:text-[#5c3a21]">
              <div dangerouslySetInnerHTML={{
                __html: (language === "en"
                  ? activeTask?.body_en || activeTask?.body_ru
                  : activeTask?.body_ru || activeTask?.body_en) ||
                  activeTask?.body ||
                  "",
              }} />

              {/* Квиз — карточка в тон пергамента, тёмное дерево по рамке */}
              {activeTask?.task_type === "quiz" && (
                <div className="mt-8 p-4 bg-[#c5a572]/50 border-2 border-[#5c3a21]/40 rounded-xl space-y-4 shadow-inner">
                  <p className="font-display text-xs font-bold uppercase text-[#5c3a21] tracking-wider">
                    {t("missionPage.pickAnswer")}
                  </p>
                  <div className="space-y-2">
                    {activeTask.data?.options?.map((opt, i) => (
                      <label key={i} className="flex items-start gap-3 p-3 bg-[#dcb98a]/70 hover:bg-[#dcb98a] border-2 border-[#5c3a21]/30 hover:border-[#5c3a21]/60 rounded-lg cursor-pointer transition-colors group">
                        <input
                          type="radio"
                          name={`quiz-${activeTask.id}`}
                          value={opt.value ?? opt}
                          checked={quizAnswers[activeTask.id] === (opt.value ?? opt)}
                          onChange={(e) => setQuizAnswers((prev) => ({ ...prev, [activeTask.id]: e.target.value }))}
                          className="mt-1 accent-[#8e1d1d]"
                        />
                        <span className="text-[#3e2723] group-hover:text-[#2a1810] font-medium transition-colors">{opt.label ?? opt}</span>
                      </label>
                    ))}
                  </div>
                  <Button
                    onClick={() => handleQuizSubmit(activeTask.id)}
                    disabled={!quizAnswers[activeTask.id] || savingTaskId === activeTask.id}
                    className="w-full justify-center mt-2 shadow-lg"
                    size="sm"
                  >
                    {savingTaskId === activeTask.id ? t("missionPage.submitting") : t("missionPage.submit")}
                  </Button>
                </div>
              )}

              {/* Кнопка завершения story-таска: rebranded в RPG-call-to-action */}
              {activeTask?.task_type === "story" && !taskProgress[activeTask.id] && (
                <div className="mt-8 pt-4">
                  <Button onClick={() => handleCompleteTask(activeTask.id, {}, 100)} className="w-full justify-center shadow-md" icon={Sparkles}>
                    {t("missionPage.acceptChallenge")}
                  </Button>
                </div>
              )}
            </div>
          </div>

          {/* Правая панель (Editor + Terminal) */}
          <div className="w-full xl:flex-1 min-h-[700px] xl:min-h-0 bg-surface dark:bg-[#1e1e1e] flex flex-col min-w-0">
            {activeTask?.task_type === "code" ? (
              <CodeRunnerPanel
                task={activeTask}
                code={codeValue}
                onChange={(val) => setCodeDrafts((prev) => ({ ...prev, [activeTask.id]: val }))}
                onTestPassed={handleTestPassed}
                onRunStateChange={handleRunState}
                inventoryCounts={inventory}
                onInventoryUpdate={handleInventoryUpdate}
              />
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center p-8 bg-surface dark:bg-[#1e1e1e] border-l border-border dark:border-[#333]">
                {/* RPG-свиток с анимированной руной. Чистый CSS,
                    без motion-библиотек — анимации через @keyframes ниже. */}
                <div className="relative max-w-md w-full">
                  {/* Капы свитка слева/справа — закрученные края */}
                  <div className="absolute left-0 top-0 bottom-0 w-3 -translate-x-2 rounded-l-full bg-gradient-to-r from-[#3a2818] via-[#5c3a21] to-[#3a2818] shadow-[inset_-1px_0_2px_rgba(0,0,0,0.5)]" />
                  <div className="absolute right-0 top-0 bottom-0 w-3 translate-x-2 rounded-r-full bg-gradient-to-l from-[#3a2818] via-[#5c3a21] to-[#3a2818] shadow-[inset_1px_0_2px_rgba(0,0,0,0.5)]" />

                  {/* Полотно пергамента */}
                  <div className="relative px-10 py-12 bg-gradient-to-br from-[#dcb98a] via-[#d4ad75] to-[#c39858] border-y-2 border-[#8b5a2b]/60 shadow-2xl text-center">
                    {/* Шум/потёртости */}
                    <div
                      className="absolute inset-0 opacity-20 pointer-events-none"
                      style={{
                        backgroundImage:
                          "radial-gradient(circle at 20% 30%, rgba(60,30,10,0.4), transparent 40%), radial-gradient(circle at 80% 70%, rgba(40,20,10,0.3), transparent 35%)",
                      }}
                    />

                    {/* Анимированная руна */}
                    <div className="relative mx-auto w-24 h-24 mb-6">
                      {/* Внешнее кольцо — медленное вращение */}
                      <svg className="absolute inset-0 w-full h-full animate-[rune-spin_12s_linear_infinite]" viewBox="0 0 100 100">
                        <circle cx="50" cy="50" r="46" fill="none" stroke="#5c3a21" strokeWidth="1.5" strokeDasharray="3 5" opacity="0.7"/>
                        <circle cx="50" cy="50" r="46" fill="none" stroke="#8e1d1d" strokeWidth="0.5" opacity="0.5"/>
                      </svg>
                      {/* Внутреннее кольцо — обратное вращение */}
                      <svg className="absolute inset-0 w-full h-full animate-[rune-spin-reverse_8s_linear_infinite]" viewBox="0 0 100 100">
                        <circle cx="50" cy="50" r="34" fill="none" stroke="#3e2723" strokeWidth="1" strokeDasharray="2 8"/>
                        {/* Четыре опорные точки руны */}
                        <circle cx="50" cy="16" r="2" fill="#8e1d1d"/>
                        <circle cx="84" cy="50" r="2" fill="#8e1d1d"/>
                        <circle cx="50" cy="84" r="2" fill="#8e1d1d"/>
                        <circle cx="16" cy="50" r="2" fill="#8e1d1d"/>
                      </svg>
                      {/* Центральный пульс */}
                      <div className="absolute inset-0 flex items-center justify-center">
                        <span className="relative inline-flex">
                          <span className="absolute inline-flex h-8 w-8 rounded-full bg-[#8e1d1d]/40 animate-ping" />
                          <span className="relative inline-flex h-8 w-8 items-center justify-center rounded-full bg-[#5c3a21] text-[#fde68a] text-lg font-display font-bold shadow-[0_0_12px_rgba(142,29,29,0.6)]">
                            ✦
                          </span>
                        </span>
                      </div>
                    </div>

                    <p className="font-display text-2xl font-bold text-[#3e2723] mb-3 tracking-wide">
                      {t("missionPage.standby.title")}
                    </p>
                    <p className="text-sm text-[#5c3a21] leading-relaxed">
                      {t("missionPage.standby.body")}
                    </p>
                  </div>
                </div>

                <style jsx>{`
                  @keyframes rune-spin {
                    from { transform: rotate(0deg); }
                    to { transform: rotate(360deg); }
                  }
                  @keyframes rune-spin-reverse {
                    from { transform: rotate(360deg); }
                    to { transform: rotate(0deg); }
                  }
                `}</style>
              </div>
            )}
          </div>
        </section>
      </div>
    </Layout>
  );
}