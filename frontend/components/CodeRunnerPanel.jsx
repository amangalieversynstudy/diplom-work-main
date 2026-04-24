import { useState } from "react";
import Button from "./Button";
import { toast } from "sonner";
import { Runner } from "../lib/api"; // ИСПРАВЛЕНО: Импортируем Runner в фигурных скобках

export default function CodeRunnerPanel({
  initialCode = "def solve():\n    # Напиши свой код здесь\n    pass\n\nsolve()",
  onSuccess,
}) {
  const [code, setCode] = useState(initialCode);
  const [output, setOutput] = useState("");
  const [isRunning, setIsRunning] = useState(false);

  const handleRunCode = async () => {
    if (!code.trim()) {
      toast.error("Код не может быть пустым!");
      return;
    }

    setIsRunning(true);
    setOutput("Запуск кода в изолированной песочнице...");

    try {
      // ИСПРАВЛЕНО: Используем правильный метод Runner.execute
      const response = await Runner.execute(code);
      
      const result = response.data;
      
      if (result.status === "success") {
        setOutput(result.output || "Код выполнен успешно (нет вывода в консоль).");
        toast.success("Код выполнен без ошибок!");
        if (onSuccess) onSuccess();
      } else {
        setOutput(`Ошибка выполнения:\n${result.output}`);
        toast.error("Ошибка в коде!");
      }
    } catch (error) {
      const errorMsg = error.response?.data?.output || "Не удалось связаться с сервером песочницы.";
      setOutput(`Системная ошибка:\n${errorMsg}`);
      toast.error("Сбой песочницы");
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="flex flex-col border border-white/20 rounded-lg overflow-hidden bg-black">
      {/* Верхняя панель (Редактор) */}
      <div className="flex-1 min-h-[300px] relative">
        <div className="absolute top-0 left-0 w-full px-4 py-2 bg-white/5 border-b border-white/10 flex justify-between items-center z-10">
          <span className="text-xs font-mono text-white/50">main.py</span>
          <Button
            size="sm"
            variant="primary"
            onClick={handleRunCode}
            disabled={isRunning}
            className="h-8 text-xs px-4"
          >
            {isRunning ? "Компиляция..." : "▶ Запустить код"}
          </Button>
        </div>
        
        <textarea
          value={code}
          onChange={(e) => setCode(e.target.value)}
          spellCheck="false"
          className="w-full h-full p-4 pt-12 bg-transparent text-sm font-mono text-white/90 resize-none focus:outline-none focus:ring-0"
          placeholder="Напиши свой Python код здесь..."
        />
      </div>

      {/* Нижняя панель (Консоль вывода) */}
      <div className="h-[150px] bg-[#0A0A0A] border-t border-white/20 p-3 flex flex-col">
        <span className="text-[10px] uppercase tracking-wider text-white/40 mb-2 font-bold">
          Консоль вывода (stdout)
        </span>
        <pre className="flex-1 overflow-y-auto text-xs font-mono text-green-400 whitespace-pre-wrap">
          {output || "> Готов к выполнению..."}
        </pre>
      </div>
    </div>
  );
}