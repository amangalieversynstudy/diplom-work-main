import Button from "./Button";
import Card from "./Card";
import { Loader2, Play } from "lucide-react";

export default function CodeRunnerPanel({
  task,
  code,
  onChange,
  onRun,
  result,
  running,
  copy,
}) {
  if (!task) return null;
  return (
    <Card tone="night" title={task.title} subtitle={copy.subtitle}>
      <textarea
        className="w-full h-48 rounded-xl bg-black/60 border border-white/10 p-3 font-mono text-sm text-white"
        value={code}
        onChange={(e) => onChange(e.target.value)}
        placeholder={copy.placeholder}
      />
      <div className="flex items-center justify-between mt-3">
        <p className="text-xs text-white/50">
          {copy.hint.replace("{language}", task.data?.language || "Python")}
        </p>
        <Button onClick={onRun} disabled={running}>
          {running ? <Loader2 className="animate-spin" size={18} /> : <Play size={18} />}
          {copy.run}
        </Button>
      </div>
      {result && (
        <div className="mt-4 space-y-2">
          <p className="text-sm text-white/70">
            {result.success ? copy.success : copy.fail}
          </p>
          {result.stdout && (
            <pre className="bg-black/50 rounded-lg p-3 text-xs text-emerald-300 border border-emerald-500/20">
              {result.stdout}
            </pre>
          )}
          {result.stderr && (
            <pre className="bg-black/50 rounded-lg p-3 text-xs text-rose-300 border border-rose-500/20">
              {result.stderr}
            </pre>
          )}
          <div className="bg-white/5 rounded-xl p-3 border border-white/10">
            <p className="text-xs uppercase tracking-[0.3em] text-white/50">
              {copy.tests}
            </p>
            <ul className="text-sm text-white/80 mt-2 space-y-1">
              {(result.tests || []).map((test) => (
                <li key={test.name} className="flex justify-between">
                  <span>{test.name}</span>
                  <span className={test.status === "passed" ? "text-emerald-300" : test.status === "warning" ? "text-amber-300" : "text-rose-300"}>
                    {test.status}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </Card>
  );
}
