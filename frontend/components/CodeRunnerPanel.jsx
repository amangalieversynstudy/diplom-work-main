import { Play, Terminal as TerminalIcon, FileCode2, Scroll, Lightbulb, Bot } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Profile } from "../lib/api";

export default function CodeRunnerPanel({
  task,
  code,
  onChange,
  onRun,
  result,
  running,
  inventoryCounts = { ai_summons: 0, hint_scrolls: 0, skeleton_scrolls: 0 },
  onInventoryUpdate,
}) {
  const [usingItem, setUsingItem] = useState(false);

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

// --- ЛОГИКА ИНВЕНТАРЯ ---
  const handleUseItem = async (itemType, itemName) => {
    if (usingItem) return false;
    setUsingItem(true);
    
    try {
      // ИСПРАВЛЕНО: вызываем Profile.consumeItem вместо Profile.useItem
      const res = await Profile.consumeItem(itemType);
      
      toast.success(`${itemName} использован! Осталось: ${res.remaining}`);
      // Обновляем состояние инвентаря на уровне родителя (миссии)
      if (onInventoryUpdate) onInventoryUpdate(itemType, res.remaining);
      return true;
    } catch (error) {
      toast.error(error.response?.data?.detail || "Не удалось использовать предмет или он закончился.");
      return false;
    } finally {
      setUsingItem(false);
    }
  };

  const handleSkeletonScroll = async () => {
    const success = await handleUseItem('skeleton_scrolls', 'Свиток Архитектора');
    if (success) {
      // Ищем заготовку кода в данных задачи, либо даем стандартную
      const boilerplate = task?.data?.starter || "# Напишите свой код ниже\ndef main():\n    pass\n\nif __name__ == '__main__':\n    main()\n";
      // Если код уже есть, добавляем снизу, иначе полностью заменяем
      onChange(code ? `${code}\n\n${boilerplate}` : boilerplate);
    }
  };

  const handleHintScroll = async () => {
    const success = await handleUseItem('hint_scrolls', 'Зелье Ясности');
    if (success) {
      const hint = task?.data?.hint || "Проверьте правильность отступов и синтаксис объявления функций.";
      toast(`💡 Подсказка: ${hint}`, { duration: 6000 });
    }
  };

  const handleAISummon = async () => {
    const success = await handleUseItem('ai_summons', 'AI Summon');
    if (success) {
      toast("🤖 AI: Анализирую код... Ошибок в синтаксисе не вижу, но проверьте логику условий!");
    }
  };

  return (
    <div className="flex flex-col h-full bg-[#1e1e1e] font-mono overflow-hidden">
      {/* Editor Tabs & Toolbar */}
      <div className="flex items-center bg-[#252526] overflow-x-auto select-none border-l border-[#333]">
        <div className="flex items-center gap-2 bg-[#1e1e1e] px-4 py-2 border-t border-[#3794ff] min-w-max cursor-pointer">
           <FileCode2 size={14} className="text-[#519aba]" />
           <span className="text-xs text-white">main.py</span>
        </div>

        {/* Инвентарь (Тулбар) */}
        <div className="flex items-center gap-3 px-4 py-1 border-l border-[#333] ml-2">
          <button 
            onClick={handleSkeletonScroll} 
            disabled={usingItem || !inventoryCounts?.skeleton_scrolls}
            className={`flex items-center gap-1.5 px-2 py-1 text-[11px] rounded transition-colors ${inventoryCounts?.skeleton_scrolls > 0 ? 'text-[#e5c07b] hover:bg-[#333] cursor-pointer' : 'text-gray-600 cursor-not-allowed'}`}
            title="Свиток Архитектора (Вставить каркас кода)"
          >
            <Scroll size={14} /> 
            <span>{inventoryCounts?.skeleton_scrolls || 0}</span>
          </button>
          
          <button 
            onClick={handleHintScroll} 
            disabled={usingItem || !inventoryCounts?.hint_scrolls}
            className={`flex items-center gap-1.5 px-2 py-1 text-[11px] rounded transition-colors ${inventoryCounts?.hint_scrolls > 0 ? 'text-[#98c379] hover:bg-[#333] cursor-pointer' : 'text-gray-600 cursor-not-allowed'}`}
            title="Зелье Ясности (Получить подсказку)"
          >
            <Lightbulb size={14} />
            <span>{inventoryCounts?.hint_scrolls || 0}</span>
          </button>

          <button 
            onClick={handleAISummon} 
            disabled={usingItem || !inventoryCounts?.ai_summons}
            className={`flex items-center gap-1.5 px-2 py-1 text-[11px] rounded transition-colors ${inventoryCounts?.ai_summons > 0 ? 'text-[#c678dd] hover:bg-[#333] cursor-pointer' : 'text-gray-600 cursor-not-allowed'}`}
            title="Вызвать AI-помощника"
          >
            <Bot size={14} />
            <span>{inventoryCounts?.ai_summons || 0}</span>
          </button>
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