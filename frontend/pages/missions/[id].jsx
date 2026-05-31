import Layout from "../../components/Layout";
import Button from "../../components/Button";
import MissionStepper from "../../components/MissionStepper";
import CodeRunnerPanel from "../../components/CodeRunnerPanel";
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
      })
      .catch((err) => {
        logger.error("Не удалось загрузить инвентарь игрока:", err);
      });

    return () => {
      active = false;
    };
    // MID-06: при смене языка миссия перезагружается с правильными title_ru/title_en
  }, [id, language]);

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
      toast.error("🛡️ Ответ неверный! Мана поглощена, попробуйте другое заклинание.");
    }
  };

  if (!mission) {
    return (
      <Layout fullBleed hideFooter>
        <div className="h-screen pt-24 bg-[#0f0f11] flex items-center justify-center text-white font-mono">
          <div className="text-center space-y-4">
            <div className="w-12 h-12 border-4 border-t-purple-500 border-gray-700 rounded-full animate-spin mx-auto"></div>
            <p className="text-gray-400 tracking-widest text-sm uppercase">Loading Quest Chronicles...</p>
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
        <div className="h-screen pt-24 bg-[#0f0f11] flex items-center justify-center px-4">
          <div className="max-w-md w-full text-center space-y-6">
            <div className="w-20 h-20 rounded-full bg-[#1a1a20] border-2 border-[#333] flex items-center justify-center mx-auto">
              <Lock size={36} className="text-[#555]" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white tracking-wide mb-2">
                Квест заблокирован
              </h1>
              <p className="text-gray-400 text-sm leading-relaxed">
                Путь к «{mission.title_ru || mission.title}» ещё закрыт.
                Для доступа необходимо завершить предыдущие квесты.
              </p>
            </div>
            {prereqs.length > 0 && (
              <div className="bg-[#141418] border border-[#222] rounded-xl p-4 text-left space-y-2">
                <p className="text-xs font-mono uppercase tracking-widest text-gray-500 mb-3">
                  Необходимые квесты:
                </p>
                {prereqs.map((pre) => (
                  <div key={pre.id} className="flex items-center gap-2 text-sm text-gray-300">
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
              ← Вернуться на карту мира
            </Button>
          </div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout fullBleed hideFooter>
      <div className="h-screen pt-24 bg-[#0f0f11] text-gray-200 font-sans flex flex-col">
        {/* Квест-шапка в RPG-стиле: deep-wood band + scroll icon + Melodrama */}
        <header className="border-b border-[#5c3a21]/40 px-8 py-4 flex items-center justify-between select-none shadow-md bg-gradient-to-r from-[#2b1d11] via-[#3a2818] to-[#2b1d11]">
          <div className="flex items-center gap-4">
            <div className="p-2.5 bg-[#8b5a2b]/25 border border-[#d4a24c]/60 rounded-xl text-[#fde68a] shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]">
              <ScrollText size={22} />
            </div>
            <div>
              <h1 className="font-display text-2xl font-bold text-[#fde68a] tracking-wide drop-shadow-[0_1px_0_rgba(0,0,0,0.4)]">
                {(language === "en"
                  ? mission.title_en || mission.title_ru
                  : mission.title_ru || mission.title_en) ||
                  mission.title}
              </h1>
              <p className="text-xs text-[#d4a24c] font-mono mt-0.5 uppercase tracking-wider">
                {t("missionPage.rewardLabel")}: <span className="text-[#fde68a] font-bold">{mission.xp_reward}</span> {t("missionPage.xpGained")}
              </p>
            </div>
          </div>
          <Button variant="secondary" size="sm" onClick={() => router.push("/worlds")}>
            &larr; На карту мира
          </Button>
        </header>

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
            {/* Заголовок-баннер */}
            <div className="px-6 py-4 border-b-2 border-[#5c3a21]/40 bg-gradient-to-r from-[#3a2818]/95 via-[#5c3a21]/90 to-[#3a2818]/95 flex items-center gap-2">
              <ScrollText size={16} className="text-[#fde68a]" />
              <p className="font-display text-sm font-bold tracking-widest text-[#fde68a] uppercase">
                {t("missionPage.questLog")}
              </p>
            </div>

            <div className="flex-1 overflow-y-auto p-4">
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
            <div className="p-4 border-t-2 border-[#5c3a21]/40 bg-gradient-to-r from-[#3a2818]/95 via-[#5c3a21]/90 to-[#3a2818]/95 font-mono text-xs text-[#d4a24c]">
              {activeTask && (
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span>Тип файла:</span>
                    <span className="text-[#fde68a] uppercase font-semibold">{activeTask.task_type}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Оценка времени:</span>
                    <span className="text-[#fde68a]">{activeTask.estimated_minutes} мин</span>
                  </div>
                  {taskProgress[activeTask.id] && (
                    <div className="mt-2 pt-2 border-t border-[#5c3a21]/40 space-y-1">
                      <p>Статус: <span className="text-[#a3e635] font-bold">Выполнено</span></p>
                      <p>Попыток: {taskProgress[activeTask.id].attempts || 1}</p>
                      <p>Рекорд: <span className="text-[#fde68a] font-bold">{taskProgress[activeTask.id].best_score || 0}</span></p>
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
            }}
          >
            {/* Header-баннер: тёмное дерево, иконка типа, fantasy title */}
            <div className="px-6 py-4 border-b-2 border-[#5c3a21]/40 bg-gradient-to-r from-[#3a2818]/95 via-[#5c3a21]/90 to-[#3a2818]/95 flex items-center gap-2">
              {activeTask?.task_type === "code"
                ? <Code2 size={16} className="text-[#d4a24c]" />
                : <BookOpen size={16} className="text-[#a3e635]" />}
              <h2 className="font-display text-base font-bold text-[#fde68a] tracking-wide truncate drop-shadow-[0_1px_0_rgba(0,0,0,0.4)]">
                {(language === "en"
                  ? activeTask?.title_en || activeTask?.title_ru
                  : activeTask?.title_ru || activeTask?.title_en) ||
                  activeTask?.title ||
                  t("missionPage.scrollTitleFallback")}
              </h2>
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
          <div className="w-full xl:flex-1 min-h-[700px] xl:min-h-0 bg-[#1e1e1e] flex flex-col min-w-0">
            {activeTask?.task_type === "code" ? (
              <CodeRunnerPanel
                task={activeTask}
                code={codeValue}
                onChange={(val) => setCodeDrafts((prev) => ({ ...prev, [activeTask.id]: val }))}
                onTestPassed={handleTestPassed}
                inventoryCounts={inventory}
                onInventoryUpdate={handleInventoryUpdate}
              />
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center p-8 bg-[#1e1e1e] border-l border-[#333]">
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