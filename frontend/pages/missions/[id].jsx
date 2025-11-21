import Layout from "../../components/Layout";
import Card from "../../components/Card";
import Button from "../../components/Button";
import Badge from "../../components/Badge";
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
import { ScrollText, Sword, Sparkles } from "lucide-react";
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
      const res = await Missions.complete(id);
      await refreshMission();
      const xp = res?.xp_added ?? 0;
      toast.success(copy.success.completed, {
        description: xp ? copy.xpGain.replace("{xp}", xp) : copy.noXp,
      });
    } catch (e) {
      const msg = e?.response?.data?.detail || copy.errors.complete;
      toast.error(copy.errors.complete, { description: msg });
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
    try {
      const result = await Runner.execute({
        language: activeTask.data?.language || "python",
        code: source,
        challenge: {
          expectedSnippet: activeTask.data?.expectedSnippet || "return",
          sampleOutput: activeTask.data?.sampleOutput,
        },
      });
      setRunnerResult(result);
      await upsertTaskProgress(activeTask.id, {
        status: result.success ? "completed" : "in_progress",
        best_score: result.score,
        attempts: (taskProgress[activeTask.id]?.attempts || 0) + 1,
        answer: { code: source, stdout: result.stdout },
      });
      toast[result.success ? "success" : "error"](
        result.success ? copy.runner.codeDone : copy.runner.codeRetry
      );
    } catch (e) {
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
      <div className="text-xs uppercase tracking-[0.35em] text-white/60 mb-2">
        {copy.recap}
        {mission?.id || id}
      </div>
      <section className="grid gap-6 md:grid-cols-[1.4fr,0.6fr] mb-6">
        <Card tone="aurora" title={mission?.title || "..."} subtitle={copy.dossier}>
          <p className="text-sm text-white/80 leading-relaxed">
            {mission?.description || copy.descr}
          </p>
          <div className="flex flex-wrap gap-2 mt-4 text-xs">
            <Badge status={missionStatusValue}>{statusLabel}</Badge>
            {completed && <Badge status="completed">{copy.status.completed}</Badge>}
          </div>
        </Card>
        <Card tone="night" title={copy.rewardTitle} subtitle={copy.rewardSubtitle}>
          <div className="text-4xl text-gold font-display">
            +{mission?.xp_reward ?? 0} XP
          </div>
          <p className="text-sm text-white/70 mt-2">
            {copy.rewardHint}
          </p>
        </Card>
      </section>

      <section className="grid gap-6 md:grid-cols-3 mb-6">
        <Card tone="default" title={copy.prerequisites} subtitle={prereq}>
          <div className="text-sm text-white/75 space-y-2">
            <p>{copy.prerequisitesHint}</p>
            <p className="text-white/60 flex items-center gap-2 text-xs uppercase tracking-[0.3em]">
              <ScrollText size={16} /> {copy.chapterLabel}: {mission?.chapter || "Python"}
            </p>
          </div>
        </Card>
        <Card tone="ember" title={copy.strategy} subtitle={copy.strategySubtitle}>
          <ul className="text-sm text-white/80 space-y-1 list-disc ml-5">
            {copy.strategyItems.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </Card>
        <Card tone="moss" title={copy.state} subtitle={copy.stateSubtitle}>
          <div className="space-y-2 text-sm">
            <p>
              {copy.started}: {started ? new Date(started).toLocaleString() : dict.common.none}
            </p>
            <p>
              {copy.completed}: {completed ? dict.common.yes : dict.common.no}
            </p>
          </div>
        </Card>
      </section>

      <section className="grid gap-6 md:grid-cols-[1.1fr,0.9fr] mb-8">
        <Card tone="night" title={copy.actions} subtitle={copy.actionsSubtitle}>
          <div className="flex flex-wrap gap-3">
            <Button onClick={onStart}>
              <Sword size={18} /> {copy.start}
            </Button>
            <Button variant="outline" onClick={onComplete}>
              <Sparkles size={18} /> {copy.complete}
            </Button>
            <Button variant="ghost" onClick={() => router.back()}>
              {copy.back}
            </Button>
          </div>
        </Card>
        <Card tone="aurora" title={copy.logTitle} subtitle={copy.logSubtitle}>
          <ul className="text-sm text-white/80 space-y-2">
            {copy.logItems.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </Card>
      </section>

      <section className="grid gap-6 lg:grid-cols-[0.8fr,1.2fr]">
        <Card tone="default" title={copy.runner.title} subtitle={copy.runner.subtitle}>
          <MissionStepper
            tasks={tasks}
            activeTaskId={activeTaskId}
            progressMap={taskProgress}
            onSelect={setActiveTaskId}
            labels={copy.runner.stepper}
          />
        </Card>
        <div className="space-y-4">
          <Card
            tone="aurora"
            title={activeTask?.title || copy.runner.emptyTitle}
            subtitle={activeTask?.task_type?.toUpperCase() || ""}
          >
            {activeTask ? (
              <div className="space-y-3 text-sm text-white/80">
                <p>{activeTask.body || copy.runner.noBody}</p>
                {activeTask?.data?.objectives && (
                  <ul className="list-disc ml-5 space-y-1">
                    {activeTask.data.objectives.map((obj) => (
                      <li key={obj}>{obj}</li>
                    ))}
                  </ul>
                )}
                {requiresPremium && (
                  <div className="border border-amber-400/40 bg-amber-400/10 rounded-xl p-3">
                    <p className="text-xs uppercase tracking-[0.35em] text-amber-200">
                      {copy.paywall.badge}
                    </p>
                    <p className="text-white/90 text-sm">{copy.paywall.message}</p>
                    <Button variant="outline" className="mt-3" onClick={() => setPaywallOpen(true)}>
                      {copy.paywall.cta}
                    </Button>
                  </div>
                )}
                {!requiresPremium && activeTask.task_type === "story" && (
                  <Button onClick={() => handleStoryComplete(activeTask)} disabled={savingTaskId === activeTask.id}>
                    {copy.runner.storyCta}
                  </Button>
                )}
                {!requiresPremium && activeTask.task_type === "quiz" && (
                  <div className="space-y-2">
                    {(activeTask.data?.options || copy.runner.quizFallback).map((opt) => {
                      const state = quizAnswers[activeTask.id];
                      const isSelected = state?.selected === opt.value;
                      return (
                        <button
                          key={opt.value}
                          type="button"
                          className={`w-full border rounded-xl px-4 py-3 text-left transition ${
                            isSelected ? "border-white/60 bg-white/5" : "border-white/10 bg-white/2 hover:border-white/40"
                          }`}
                          onClick={() => handleQuizPick(activeTask, opt)}
                        >
                          <p className="font-semibold">{opt.label}</p>
                          {isSelected && (
                            <p className="text-xs text-white/60">
                              {state?.isCorrect ? copy.runner.quizCorrect : copy.runner.quizWrong}
                            </p>
                          )}
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            ) : (
              <p className="text-sm text-white/60">{copy.runner.emptyBody}</p>
            )}
            {activeProgress && (
              <div className="mt-4 grid grid-cols-2 gap-3 text-xs text-white/60">
                <div>
                  <p className="uppercase tracking-[0.3em]">{copy.runner.status}</p>
                  <p className="text-white">{activeProgress.status}</p>
                </div>
                <div>
                  <p className="uppercase tracking-[0.3em]">{copy.runner.attempts}</p>
                  <p className="text-white">{activeProgress.attempts || 0}</p>
                </div>
                <div>
                  <p className="uppercase tracking-[0.3em]">{copy.runner.score}</p>
                  <p className="text-white">{activeProgress.best_score || 0}</p>
                </div>
                <div>
                  <p className="uppercase tracking-[0.3em]">{copy.runner.updated}</p>
                  <p className="text-white">
                    {activeProgress.last_submitted_at
                      ? new Date(activeProgress.last_submitted_at).toLocaleString()
                      : copy.none}
                  </p>
                </div>
              </div>
            )}
          </Card>
          {!requiresPremium && activeTask?.task_type === "code" && (
            <CodeRunnerPanel
              task={activeTask}
              code={codeValue}
              onChange={(val) => setCodeDrafts((prev) => ({ ...prev, [activeTask.id]: val }))}
              onRun={handleRunCode}
              result={runnerResult}
              running={runnerLoading}
              copy={copy.runner.codePanel}
            />
          )}
        </div>
      </section>

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
