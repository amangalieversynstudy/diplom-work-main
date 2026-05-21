import Layout from "../../components/Layout";
import Button from "../../components/Button";
import MissionStepper from "../../components/MissionStepper";
import CodeRunnerPanel from "../../components/CodeRunnerPanel";
import PaywallModal from "../../components/PaywallModal";
import { useRouter } from "next/router";
import { toast } from "sonner";
import {
  Missions,
  TaskProgressAPI,
  Payments,
  Profile, // Импортируем Profile для работы с инвентарем
} from "../../lib/api";
import { useEffect, useMemo, useState } from "react";
import { Sword, Sparkles, Code2, BookOpen } from "lucide-react";

export default function MissionDetail() {
  const router = useRouter();
  const { id } = router.query;
  const [mission, setMission] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [activeTaskId, setActiveTaskId] = useState(null);
  const [taskProgress, setTaskProgress] = useState({});
  const [codeDrafts, setCodeDrafts] = useState({});
  const [paywallOpen, setPaywallOpen] = useState(false);
  const [paymentState, setPaymentState] = useState(null);
  const [paymentLoading, setPaymentLoading] = useState(false);
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

  const requiresPremium = useMemo(() => {
    if (!mission?.track_is_premium) return false;
    if (mission?.user_has_premium) return false;
    return activeTask?.is_required ?? true;
  }, [mission, activeTask]);

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
        toast.error("Не удалось загрузить данные квеста.");
      });

    // 2. Загружаем прогресс задач
    TaskProgressAPI.list(id)
      .then((progressList) => {
        if (!active) return;
        const mapping = {};
        const drafts = {};
        progressList.forEach((p) => {
          mapping[p.task_id] = p;
          if (p.answer && p.answer.code) {
            drafts[p.task_id] = p.answer.code;
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
      .catch(() => {
        console.error("Не удалось загрузить инвентарь игрока.");
      });

    return () => {
      active = false;
    };
  }, [id]);

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
    toast.success("Испытание пройдено! Отправка отчёта на сервер...");
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

      toast.success("Шаг квеста успешно зафиксирован!");

      // Автоматический переход на следующий шаг
      const currentIndex = tasks.findIndex((t) => t.id === taskId);
      if (currentIndex !== -1 && currentIndex < tasks.length - 1) {
        setActiveTaskId(tasks[currentIndex + 1].id);
      } else {
        // Если это была последняя задача, проверяем статус всей миссии
        Missions.complete(id)
          .then(() => toast.success("Поздравляем! Легендарный квест полностью завершен!"))
          .catch(() => {});
      }
    } catch (e) {
      toast.error("Не удалось сохранить прогресс шага.");
    } finally {
      setSavingTaskId(false);
    }
  };

  const handleQuizSubmit = (taskId) => {
    const userAnswer = quizAnswers[taskId];
    const currentTask = tasks.find((t) => t.id === taskId);
    if (!currentTask) return;

    const correctAnswer = currentTask.data?.correct_answer;
    if (String(userAnswer).trim().toLowerCase() === String(correctAnswer).trim().toLowerCase()) {
      handleCompleteTask(taskId, { selected: userAnswer }, 100);
    } else {
      toast.error("🛡️ Ответ неверный! Мана поглощена, попробуйте другое заклинание.");
    }
  };

  const handleCheckout = async () => {
    if (!id || paymentLoading) return;
    setPaymentLoading(true);
    setPaymentState("initiating");
    try {
      const res = await Payments.checkoutTrack(mission?.track_id);
      if (res.checkout_url) {
        window.location.href = res.checkout_url;
      } else {
        toast.error("Провайдер не вернул шлюз оплаты.");
        setPaymentState("error");
      }
    } catch (e) {
      toast.error("Ошибка инициализации транзакции.");
      setPaymentState("error");
    } finally {
      setPaymentLoading(false);
    }
  };

  if (!mission) {
    return (
      <Layout>
        <div className="min-h-screen bg-[#0f0f11] flex items-center justify-center text-white font-mono">
          <div className="text-center space-y-4">
            <div className="w-12 h-12 border-4 border-t-purple-500 border-gray-700 rounded-full animate-spin mx-auto"></div>
            <p className="text-gray-400 tracking-widest text-sm uppercase">Loading Quest Chronicles...</p>
          </div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="min-h-screen bg-[#0f0f11] text-gray-200 font-sans flex flex-col">
        {/* Квест-Линия Шапка */}
        <header className="bg-[#141418] border-b border-[#222] px-8 py-4 flex items-center justify-between select-none shadow-md">
          <div className="flex items-center gap-4">
            <div className="p-2.5 bg-purple-900/30 border border-purple-500/40 rounded-xl text-purple-400">
              <Sword size={22} className="animate-pulse" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-white tracking-wide">{mission.title_ru || mission.title}</h1>
              <p className="text-xs text-purple-400/80 font-mono mt-0.5 uppercase tracking-wider">
                Reward: <span className="text-white font-bold">{mission.xp_reward}</span> XP Gained
              </p>
            </div>
          </div>
          <Button variant="secondary" size="sm" onClick={() => router.push("/worlds")}>
            &larr; На карту мира
          </Button>
        </header>

        {/* Основной контент */}
        <section className="flex-1 flex min-h-0 overflow-hidden">
          {/* Левая панель (Explorer / Stepper) */}
          <div className="w-[360px] bg-[#141418] border-r border-[#222] flex flex-col select-none shadow-2xl z-10">
            <div className="px-6 py-4 border-b border-[#222] bg-[#111114]">
              <p className="text-xs font-mono font-bold tracking-widest text-gray-400 uppercase">Quest Logistics</p>
            </div>

            <div className="flex-1 overflow-y-auto p-4">
              <MissionStepper
                tasks={tasks}
                activeId={activeTaskId}
                progress={taskProgress}
                onSelect={(taskId) => {
                  setActiveTaskId(taskId);
                }}
              />
            </div>

            {/* Статистика текущей ноды */}
            <div className="p-4 bg-[#111114] border-t border-[#222] font-mono text-xs text-gray-400">
              {activeTask && (
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span>Тип файла:</span>
                    <span className="text-purple-400 uppercase font-semibold">{activeTask.task_type}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Оценка времени:</span>
                    <span className="text-white">{activeTask.estimated_minutes} мин</span>
                  </div>
                  {taskProgress[activeTask.id] && (
                    <div className="mt-2 pt-2 border-t border-[#222] space-y-1">
                      <p>Статус: <span className="text-green-400 font-bold">Выполнено</span></p>
                      <p>Попыток: {taskProgress[activeTask.id].attempts || 1}</p>
                      <p>Рекорд: <span className="text-yellow-400 font-bold">{taskProgress[activeTask.id].best_score || 0}</span></p>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Центральная панель (Инструкции / Контент шага) */}
          <div className="w-[450px] bg-[#111114] flex flex-col border-r border-[#222] min-w-0">
            <div className="px-6 py-4 border-b border-[#222] bg-[#141418] flex items-center gap-2">
              {activeTask?.task_type === "code" ? <Code2 size={16} className="text-blue-400" /> : <BookOpen size={16} className="text-green-400" />}
              <h2 className="text-sm font-bold text-white tracking-wide truncate">
                {activeTask?.title_ru || activeTask?.title || "Описание свитка"}
              </h2>
            </div>

            <div className="flex-1 overflow-y-auto p-6 prose prose-invert max-w-none text-sm text-gray-300 leading-relaxed space-y-4">
              <div dangerouslySetInnerHTML={{ __html: activeTask?.body_ru || activeTask?.body || "" }} />

              {/* Рендеринг Квиза / Теста */}
              {activeTask?.task_type === "quiz" && (
                <div className="mt-8 p-4 bg-[#141418] border border-[#26262b] rounded-xl space-y-4 shadow-inner">
                  <p className="font-mono text-xs font-bold uppercase text-purple-400 tracking-wider">Выберите верный ответ:</p>
                  <div className="space-y-2">
                    {activeTask.data?.options?.map((opt, i) => (
                      <label key={i} className="flex items-start gap-3 p-3 bg-[#1a1a20] hover:bg-[#202029] border border-[#26262b] rounded-lg cursor-pointer transition-colors group">
                        <input
                          type="radio"
                          name={`quiz-${activeTask.id}`}
                          value={opt.value ?? opt}
                          checked={quizAnswers[activeTask.id] === (opt.value ?? opt)}
                          onChange={(e) => setQuizAnswers((prev) => ({ ...prev, [activeTask.id]: e.target.value }))}
                          className="mt-1 text-purple-500 focus:ring-purple-500 focus:ring-offset-0 bg-[#141418] border-[#333]"
                        />
                        <span className="text-gray-300 group-hover:text-white transition-colors">{opt.label ?? opt}</span>
                      </label>
                    ))}
                  </div>
                  <Button
                    onClick={() => handleQuizSubmit(activeTask.id)}
                    disabled={!quizAnswers[activeTask.id] || savingTaskId === activeTask.id}
                    className="w-full justify-center mt-2 shadow-lg"
                    size="sm"
                  >
                    {savingTaskId === activeTask.id ? "Применение..." : "Произнести ответ"}
                  </Button>
                </div>
              )}

              {/* Рендеринг Теории (Кнопка завершения) */}
              {activeTask?.task_type === "story" && !taskProgress[activeTask.id] && (
                <div className="mt-8 pt-4">
                  <Button onClick={() => handleCompleteTask(activeTask.id, {}, 100)} className="w-full justify-center shadow-md" icon={Sparkles}>
                    Материал усвоен +Продолжить
                  </Button>
                </div>
              )}
            </div>
          </div>

          {/* Правая панель (Editor + Terminal) */}
          <div className="flex-1 bg-[#1e1e1e] flex flex-col min-w-0">
            {!requiresPremium && activeTask?.task_type === "code" ? (
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
                <Code2 size={80} className="text-[#333] mb-6" />
                <p className="text-2xl font-bold text-[#858585] mb-2">Editor Standby</p>
                <p className="text-sm text-[#555] max-w-sm text-center">
                  Select a &ldquo;Code&rdquo; file from the Explorer on the left to open the editor and terminal.
                </p>
              </div>
            )}
          </div>
        </section>
      </div>

      <PaywallModal
        open={paywallOpen}
        onClose={() => setPaywallOpen(false)}
        onCheckout={handleCheckout}
        loading={paymentLoading}
        state={paymentState}
      />
    </Layout>
  );
}