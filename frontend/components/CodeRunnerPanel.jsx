import { Play, Terminal as TerminalIcon, FileCode2 } from "lucide-react";

export default function CodeRunnerPanel({
  task,
  code,
  onChange,
  onRun,
  result,
  running,
}) {
  let outputText = "> Ожидание команд...\n";
  if (running) {
    outputText = "user@academy:~$ python main.py\n\n[Выполнение кода в безопасной песочнице...]";
  } else if (result) {
    outputText = "user@academy:~$ python main.py\n\n";
    if (result.status === "success") {
      outputText += result.output || "Код выполнен успешно (нет вывода).";
    } else {
      outputText += `Ошибка:\n${result.output || result.error || "Неизвестная ошибка"}`;
    }
  }

  const lines = code ? code.split('\n').length : 1;
  const lineArray = Array.from({ length: Math.max(25, lines) }, (_, i) => i + 1);

  return (
    <div className="flex flex-col h-full bg-[#1e1e1e] font-mono overflow-hidden">
      {/* Editor Tabs */}
      <div className="flex items-center bg-[#252526] overflow-x-auto select-none border-l border-[#333]">
        <div className="flex items-center gap-2 bg-[#1e1e1e] px-4 py-2 border-t border-[#3794ff] min-w-max cursor-pointer">
           <FileCode2 size={14} className="text-[#519aba]" />
           <span className="text-xs text-white">main.py</span>
        </div>
        <div className="flex-1" />
        <div className="px-3 flex items-center bg-[#252526]">
          <button 
            onClick={onRun}
            disabled={running}
            className="flex items-center gap-1.5 px-3 py-1 rounded bg-[#0e639c] hover:bg-[#1177bb] text-white text-xs transition-colors"
          >
            <Play size={12} fill={running ? "none" : "currentColor"} className={running ? "animate-pulse text-[#cca700]" : "text-white"} />
            {running ? "Выполнение..." : "Run Code"}
          </button>
        </div>
        
      </div>

      {/* Breadcrumbs */}
      <div className="flex items-center gap-1.5 px-4 py-1.5 text-[11px] text-[#cccccc] bg-[#1e1e1e] border-b border-[#333] border-l select-none shadow-sm z-10">
         <span className="hover:text-white cursor-pointer">rpg-academy</span>
         <span className="opacity-50">&gt;</span>
         <span className="hover:text-white cursor-pointer">mission-{task?.mission || 'X'}</span>
         <span className="opacity-50">&gt;</span>
         <span className="hover:text-white cursor-pointer">main.py</span>
      </div>

      {/* Text Area */}
      <div className="flex-1 relative bg-[#1e1e1e] flex border-l border-[#333]">
        {/* Line numbers */}
        <div className="w-12 bg-[#1e1e1e] border-r border-[#333] flex flex-col items-end py-4 pr-3 text-[#858585] text-xs select-none overflow-hidden font-mono">
           {lineArray.map(n => <span key={n} className="leading-6 opacity-50">{n}</span>)}
        </div>
        <textarea
          value={code || ""}
          onChange={(e) => onChange(e.target.value)}
          spellCheck="false"
          className="w-full h-full p-4 bg-transparent text-[13px] font-mono text-[#d4d4d4] resize-none focus:outline-none focus:ring-0 leading-6"
          placeholder="# Напиши свой код здесь..."
        />
      </div>

      {/* Нижняя панель (Консоль вывода) */}
      <div className="h-[250px] flex flex-col bg-[#1e1e1e] border-t border-l border-[#333]">
        <div className="flex items-center gap-4 px-4 pt-2 border-b border-[#333] select-none">
           <span className="text-[11px] uppercase tracking-wider text-white border-b border-white pb-2 font-semibold flex items-center gap-2">
             <TerminalIcon size={14} /> TERMINAL
           </span>
           <span className="text-[11px] uppercase tracking-wider text-[#858585] pb-2 cursor-pointer hover:text-white">
             OUTPUT
           </span>
           <span className="text-[11px] uppercase tracking-wider text-[#858585] pb-2 cursor-pointer hover:text-white">
             PROBLEMS
           </span>
        </div>
        <div className="p-4 flex-1 overflow-y-auto">
          <pre className={`text-[13px] font-mono whitespace-pre-wrap leading-relaxed ${result && result.status !== "success" ? "text-[#f14c4c]" : "text-[#cccccc]"}`}>
            {outputText}<span className="animate-pulse font-bold">_</span>
          </pre>
        </div>
      </div>
    </div>
  );
}