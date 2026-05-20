import Layout from "../../components/Layout";
import Button from "../../components/Button";
import MissionStepper from "../../components/MissionStepper";
import CodeRunnerPanel from "../../components/CodeRunnerPanel";
import PaywallModal from "../../components/PaywallModal";
import { useRouter } from "next/router";
import { toast } from "sonner";
import {
  Missions,
  MissionTasks,
  TaskProgressAPI,
  missionStatus,
  Runner,
  Payments,
} from "../../lib/api";
import { useEffect, useMemo, useState } from "react";
import { Sword, Sparkles, Code2, BookOpen } from "lucide-react";
import { useDictionary } from "../../lib/i18n";

export default function MissionDetail() {
  const router = useRouter();
  const { id } = router.query;
  const [mission, setMission] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [activeTaskId, setActiveTaskId] = useState(null);
  const [taskProgress, setTaskProgress] = useState({});
  const [codeDrafts, setCodeDrafts] = useState({});
  const [runnerResult, setRunnerResult] = useState(null);
  const [runnerLoading, setRunnerLoading] = useState(false);
  const [paywallOpen, setPaywallOpen] = useState(false);
  const [paymentState, setPaymentState] = useState(null);
  const [paymentLoading, setPaymentLoading] = useState(false);
  const [quizAnswers, setQuizAnswers] = useState({});
  const [savingTaskId, setSavingTaskId] = useState(null);
  const dict = useDictionary();
  const copy = dict.missions;

  useEffect(() => {
    if (!id) return;
    Missions.get(id)
      .then(setMission)
      .catch(() => toast.error(copy.errors.load));
  }, [id, copy.errors.load]);

  useEffect(() => {
    if (!mission) return;
    if (mission.tasks?.length) {
      const sorted = [...mission.tasks].sort((a, b) => a.order - b.order);
      setTasks(sorted);
      setActiveTaskId((prev) => prev ?? sorted[0]?.id ?? null);
      return;
    }
    MissionTasks.list(mission.id)
      .then((list) => {
        // Внедряем обучающую цепочку "Hello World" для самой первой миссии
        if (list.length === 0 && (mission.order === 1 || mission.title === "Intro" || id === "1")) {
          list = [
            {
              id: "task-hw-story",
              task_type: "story",
              title: "Традиция магов кода",
              body: "Добро пожаловать в Академию!\n\nПуть каждого разработчика начинается с одного и того же древнего ритуала. В 1978 году была написана первая программа, которая просто выводила текст на экран. С тех пор это стало великим обрядом посвящения.\n\nТебе предстоит запустить свою первую программу и поприветствовать этот мир.",
              estimated_minutes: 2,
              xp_reward: 10
            },
            {
              id: "task-hw-quiz",
              task_type: "quiz",
              title: "Проверка знаний",
              body: "Какая встроенная функция в Python используется для вывода текста в консоль?",
              estimated_minutes: 1,
              xp_reward: 15,
              data: {
                options: [
                  { label: "echo('Hello World')", value: "a", isCorrect: false },
                  { label: "print('Hello World')", value: "b", isCorrect: true },
                  { label: "console.log('Hello World')", value: "c", isCorrect: false }
                ]
              }
            },
            {
              id: "task-hw-code",
              task_type: "code",
              title: "Первое заклинание",
              body: "Напиши код, который выведет строку 'Hello World' в консоль. Это докажет, что твой терминал настроен верно.",
              estimated_minutes: 5,
              xp_reward: 25,
              data: {
                language: "python",
                starter: "# Твой первый код\ndef greet():\n    # Напиши функцию вывода 'Hello World'\n    pass\n\ngreet()",
                expectedSnippet: "hello",
                sampleOutput: "Hello World\n\n> Программа успешно выполнена!"
              }
            }
          ];
        }
        setTasks(list);
        setActiveTaskId(list[0]?.id ?? null);
      })
      .catch(() => setTasks([]));
  }, [mission]);

  useEffect(() => {
    if (!mission) return;
    TaskProgressAPI.list()
      .then((entries) => {
        const map = entries.reduce((acc, entry) => {
          acc[entry.task] = entry;
          return acc;
        }, {});
        setTaskProgress(map);
      })
      .catch(() => {});
  }, [mission]);

  const activeTask = useMemo(() => {
    if (!tasks.length) return null;
    return tasks.find((task) => task.id === activeTaskId) || tasks[0];
  }, [tasks, activeTaskId]);

  useEffect(() => {
    if (!activeTask || activeTask.task_type !== "code") return;
    setRunnerResult(null);
    setCodeDrafts((prev) => {
      if (prev[activeTask.id]) return prev;
      return {
        ...prev,
        [activeTask.id]: activeTask.data?.starter || "def solution():\n    return 'Привет'",
      };
    });
  }, [activeTask]);

  const refreshMission = async () => {
    const updated = await Missions.get(id);
    setMission(updated);
  };

  const onStart = async () => {
    try {
      await Missions.start(id);
      await refreshMission();
      toast.success(copy.success.started);
    } catch (e) {
      const msg = e?.response?.data?.detail || copy.errors.start;
      toast.error(copy.errors.start, { description: msg });
    }
  };

  const onComplete = async () => {
    try {
      // Отправляем запрос на завершение миссии
      const res = await Missions.complete(id);
      
      // Поддерживаем разные форматы ответа бэкенда (на случай если там xp_added или xp_earned)
      const xp = res?.xp_earned ?? res?.xp_added ?? 0;
      const leveledUp = res?.leveled_up;

      toast.success(`Миссия пройдена! Получено ${xp} XP ⚔️`, {
        duration: 4000,
      });

      if (leveledUp) {
        toast.success("🎉 УРОВЕНЬ ПОВЫШЕН! 🎉", { 
          duration: 6000,
          description: "Ваши характеристики выросли. Так держать!" 
        });
      }

      // После успеха эпично возвращаем на карту миров
      router.push("/worlds");

    } catch (e) {
      console.error("Ошибка при завершении миссии:", e);
      const msg = e?.response?.data?.detail || "Связь с сервером потеряна. Прогресс не сохранен.";
      toast.error(copy.errors.complete || "Ошибка", { description: msg });
    }
  };

  const upsertTaskProgress = async (taskId, payload = {}) => {
    if (!taskId) return null;
    setSavingTaskId(taskId);
    try {
      const existing = taskProgress[taskId];
      const body = { task: taskId, ...payload };
      const entry = existing
        ? await TaskProgressAPI.update(existing.id, body)
        : await TaskProgressAPI.create(body);
      setTaskProgress((prev) => ({ ...prev, [taskId]: entry }));
      return entry;
    } finally {
      setSavingTaskId(null);
    }
  };

  const handleStoryComplete = async (task) => {
    if (!task) return;
    try {
      const attempts = (taskProgress[task.id]?.attempts || 0) + 1;
      await upsertTaskProgress(task.id, { status: "completed", attempts });
      toast.success(copy.runner.storyDone);
    } catch (e) {
      toast.error(copy.runner.saveError);
    }
  };

  const handleQuizPick = async (task, option) => {
    if (!task || !option) return;
    const isCorrect =
      option.isCorrect ?? option.correct ?? option.value === task.data?.answer;
    setQuizAnswers((prev) => ({
      ...prev,
      [task.id]: { selected: option.value, isCorrect },
    }));
    try {
      await upsertTaskProgress(task.id, {
        status: isCorrect ? "completed" : "in_progress",
        best_score: isCorrect ? 100 : 50,
        attempts: (taskProgress[task.id]?.attempts || 0) + 1,
        answer: { selected: option.value },
      });
      toast[isCorrect ? "success" : "error"](
        isCorrect ? copy.runner.quizCorrect : copy.runner.quizWrong
      );
    } catch (e) {
      toast.error(copy.runner.saveError);
    }
  };

  const handleRunCode = async () => {
    if (!activeTask) return;
    const source = codeDrafts[activeTask.id] || "";
    setRunnerLoading(true);
    setRunnerResult(null); // Очищаем старый результат на время загрузки
    try {
      // Отправляем чистый код на сервер песочницы
      const response = await Runner.execute(source);
      const result = response.data;
      
      setRunnerResult(result);
      
      const isSuccess = result.status === "success";
      
      await upsertTaskProgress(activeTask.id, {
        status: isSuccess ? "completed" : "in_progress",
        best_score: isSuccess ? 100 : 0,
        attempts: (taskProgress[activeTask.id]?.attempts || 0) + 1,
        answer: { code: source, stdout: result.output },
      });
      toast[isSuccess ? "success" : "error"](
        isSuccess ? copy.runner.codeDone : copy.runner.codeRetry
      );
    } catch (e) {
      setRunnerResult({
        status: "error",
        output: "Сервис песочницы недоступен. Проверьте подключение к бэкенду."
      });
      toast.error(copy.runner.runnerError);
    } finally {
      setRunnerLoading(false);
    }
  };

  const handleCheckout = async (planId) => {
    setPaymentLoading(true);
    try {
      const state = await Payments.checkout({ plan: planId });
      setPaymentState(state);
      toast.success(copy.paywall.success);
      setPaywallOpen(false);
    } catch (e) {
      toast.error(copy.paywall.error);
    } finally {
      setPaymentLoading(false);
    }
  };

  const activeProgress = activeTask ? taskProgress[activeTask.id] : null;
  const missionStatusValue = mission ? missionStatus(mission) : "locked";
  const requiresPremium = activeTask?.data?.requiresPremium && !paymentState?.success;
  const codeValue = activeTask ? codeDrafts[activeTask.id] || "" : "";

  const prereq = mission?.prerequisites?.length
    ? mission.prerequisites.map((p) => p.title).join(", ")
    : copy.none;
  const statusLabel = copy.status[missionStatusValue] || missionStatusValue;
  const completed = mission?.user_progress?.completed;
  const started = mission?.user_progress?.started_at;

  return (
    <Layout>
      <div className="max-w-[1500px] mx-auto pt-24 pb-10 px-4 transition-colors duration-300">
        
        {/* ── Заголовок и Действия ── */}
        <header className="flex flex-col md:flex-row justify-between items-start md:items-end gap-4 mb-6">
          <div>
            <p className="text-xs uppercase tracking-widest text-[#3794ff] mb-2 font-mono">
              {copy.recap} {mission?.id || id}
            </p>
            <h1 className="text-3xl md:text-4xl font-display font-bold text-text">
              {mission?.title || "..."}
            </h1>
          </div>
          
          <div className="flex flex-wrap items-center gap-3">
            {completed && (
              <span className="text-[#89d185] text-xs font-bold border border-[#89d185]/30 px-3 py-1.5 rounded bg-[#89d185]/10">
                {copy.status.completed}
              </span>
            )}
            
            {!completed && (
              <Button onClick={onStart} className="bg-[#0e639c] hover:bg-[#1177bb] border-none text-white rounded-md text-sm shadow-none px-4 py-2">
                <Sword size={16} className="mr-2" /> {copy.start}
              </Button>
            )}

            <Button 
              variant="outline" 
              onClick={onComplete} 
              className="border border-[#89d185] text-[#89d185] hover:bg-[#89d185] hover:text-[#1e1e1e] rounded-md text-sm shadow-[0_0_10px_rgba(137,209,133,0.1)] hover:shadow-[0_0_15px_rgba(137,209,133,0.4)] px-4 py-2 transition-all duration-300 bg-[#1e1e1e]"
            >
              <Sparkles size={16} className="mr-2" /> {copy.complete || "Завершить миссию"}
            </Button>

            <Button variant="ghost" onClick={() => router.back()} className="text-[#858585] hover:text-white hover:bg-[#333] rounded-md text-sm px-4 py-2 transition-colors">
              {copy.back || "Назад"}
            </Button>
          </div>
        </header>

        {/* ── ИНТЕРФЕЙС VS CODE ── */}
        <section className="flex flex-col lg:flex-row border border-[#333] rounded-lg overflow-hidden shadow-2xl h-[85vh] min-h-[700px] bg-[#1e1e1e] font-sans">
          
          {/* Activity Bar (Тонкая левая полоса) */}
          <div className="hidden lg:flex w-12 bg-[#333333] flex-col items-center py-4 gap-6 shrink-0 z-10 border-r border-[#252526]">
            <div className="relative group cursor-pointer w-full flex justify-center">
              <div className="absolute left-0 top-1/2 -translate-y-1/2 h-8 w-[2px] bg-white"></div>
              <BookOpen size={24} className="text-white" />
            </div>
            <Code2 size={24} className="text-[#858585] hover:text-white cursor-pointer transition-colors" />
            <Sparkles size={24} className="text-[#858585] hover:text-white cursor-pointer transition-colors" />
          </div>

          {/* Левая панель (Explorer & Lore) */}
          <div className="w-full lg:w-[320px] xl:w-[380px] bg-[#252526] border-r border-[#333] flex flex-col shrink-0">
            <div className="text-[11px] uppercase tracking-wider px-4 py-3 text-[#cccccc] font-semibold flex items-center">
              EXPLORER
            </div>
            
            {/* Файловое дерево (Степпер) */}
            <div className="flex flex-col">
              <div className="flex items-center px-1 py-1 cursor-pointer text-[#cccccc] bg-[#252526] hover:bg-[#2a2d2e] font-bold text-[10px] uppercase tracking-wider">
                <span className="mr-1">▼</span> MISSION TASKS
              </div>
              <div className="pb-2 border-b border-[#333]">
                <MissionStepper
                  tasks={tasks}
                  activeTaskId={activeTaskId}
                  progressMap={taskProgress}
                  onSelect={setActiveTaskId}
                  labels={copy.runner.stepper}
                />
              </div>
            </div>

            {/* Markdown Preview (Лор) */}
            <div className="flex flex-col flex-1 overflow-hidden">
              <div className="flex items-center px-1 py-1 cursor-pointer text-[#cccccc] bg-[#252526] hover:bg-[#2a2d2e] font-bold text-[10px] uppercase tracking-wider">
                <span className="mr-1">▼</span> DESCRIPTION.md
              </div>
              <div className="flex-1 overflow-y-auto px-5 py-6 text-sm text-[#cccccc] bg-[#1e1e1e]">
                <h2 className="text-2xl font-bold text-white mb-6 pb-2 border-b border-[#333]">
                  {activeTask?.title || copy.runner.emptyTitle}
                </h2>
                
                {activeTask ? (
                  <div className="space-y-6">
                    <div className="whitespace-pre-wrap leading-relaxed text-[13px] text-[#d4d4d4] font-mono">
                      {activeTask.body || copy.runner.noBody}
                    </div>
                    
                    {activeTask?.data?.objectives && (
                      <div className="bg-[#252526] border border-[#333] rounded p-4 mt-6">
                        <h4 className="text-[11px] font-bold uppercase tracking-widest text-[#3794ff] mb-2">Objectives</h4>
                        <ul className="list-disc ml-5 space-y-1 text-[#cccccc]">
                          {activeTask.data.objectives.map((obj) => (
                            <li key={obj}>{obj}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    
                    {requiresPremium && (
                      <div className="border border-[#cca700]/50 bg-[#cca700]/10 rounded-md p-4 mt-6">
                        <p className="text-[11px] font-bold uppercase tracking-widest text-[#cca700] mb-2">
                          {copy.paywall.badge}
                        </p>
                        <p className="text-[#cccccc] text-sm mb-4">{copy.paywall.message}</p>
                        <Button className="w-full bg-[#cca700] hover:bg-[#b39300] text-[#1e1e1e] border-none rounded-sm" onClick={() => setPaywallOpen(true)}>
                          {copy.paywall.cta}
                        </Button>
                      </div>
                    )}
                    
                    {!requiresPremium && activeTask.task_type === "story" && (
                      <div className="pt-4 border-t border-[#333]">
                        <Button className="w-full bg-[#0e639c] hover:bg-[#1177bb] text-white border-none rounded-sm text-sm shadow-none" onClick={() => handleStoryComplete(activeTask)} disabled={savingTaskId === activeTask.id}>
                          {copy.runner.storyCta}
                        </Button>
                      </div>
                    )}
                    
                    {!requiresPremium && activeTask.task_type === "quiz" && (
                      <div className="space-y-2 pt-4 border-t border-[#333]">
                        <p className="text-[11px] font-bold text-[#858585] uppercase mb-3">Select the correct answer:</p>
                        {(activeTask.data?.options || copy.runner.quizFallback).map((opt) => {
                          const state = quizAnswers[activeTask.id];
                          const isSelected = state?.selected === opt.value;
                          return (
                            <button
                              key={opt.value}
                              type="button"
                              className={`w-full border rounded-sm px-4 py-3 text-left transition-all duration-200 ${
                                isSelected 
                                  ? "border-[#0e639c] bg-[#0e639c]/20 text-white" 
                                  : "border-[#333] bg-[#1e1e1e] text-[#cccccc] hover:border-[#858585] hover:bg-[#2d2d2d]"
                              }`}
                              onClick={() => handleQuizPick(activeTask, opt)}
                            >
                              <p className="font-medium text-sm">{opt.label}</p>
                              {isSelected && (
                                <p className="text-xs mt-1">
                                  {state?.isCorrect ? "✅ " + copy.runner.quizCorrect : "❌ " + copy.runner.quizWrong}
                                </p>
                              )}
                            </button>
                          );
                        })}
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="text-sm text-[#858585]">{copy.runner.emptyBody}</p>
                )}
                
                {activeProgress && (
                  <div className="mt-8 pt-4 border-t border-[#333] grid grid-cols-2 gap-4 text-[11px]">
                    <div>
                      <p className="text-[#858585] mb-1 uppercase">Status</p>
                      <p className="text-[#89d185] font-mono">{activeProgress.status}</p>
                    </div>
                    <div>
                      <p className="text-[#858585] mb-1 uppercase">Score</p>
                      <p className="text-[#cca700] font-mono">{activeProgress.best_score || 0}</p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Правая панель (Editor + Terminal) */}
          <div className="flex-1 bg-[#1e1e1e] flex flex-col min-w-0">
            {!requiresPremium && activeTask?.task_type === "code" ? (
              <CodeRunnerPanel
                task={activeTask}
                code={codeValue}
                onChange={(val) => setCodeDrafts((prev) => ({ ...prev, [activeTask.id]: val }))}
                onRun={handleRunCode}
                result={runnerResult}
                running={runnerLoading}
              />
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center p-8 bg-[#1e1e1e] border-l border-[#333]">
                <Code2 size={80} className="text-[#333] mb-6" />
                <p className="text-2xl font-bold text-[#858585] mb-2">Editor Standby</p>
                <p className="text-sm text-[#555] max-w-sm text-center">
                  Select a "Code" file from the Explorer on the left to open the editor and terminal.
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
        copy={copy.paywall}
      />
    </Layout>
  );
}
