/**
 * RPG-стилизованный confirm-модал. Заменяет нативный window.confirm(),
 * который чужеродно выглядит в тёмной игровой теме.
 *
 * Использование:
 *   const [confirm, setConfirm] = useState(null);
 *   setConfirm({
 *     title: "Покинуть таверну?",
 *     message: "Прогресс будет потерян.",
 *     onConfirm: () => doStuff(),
 *   });
 *   <ConfirmModal data={confirm} onClose={() => setConfirm(null)} />
 */

import { useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { AlertTriangle, X } from "lucide-react";
import Button from "./Button";

export default function ConfirmModal({ data, onClose }) {
  const open = Boolean(data);

  // Esc закрывает модал
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => {
      if (e.key === "Escape") onClose?.();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const handleConfirm = () => {
    data?.onConfirm?.();
    onClose?.();
  };

  const handleCancel = () => {
    data?.onCancel?.();
    onClose?.();
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.18 }}
          onClick={handleCancel}
          className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/80 backdrop-blur-sm px-4"
        >
          <motion.div
            initial={{ scale: 0.92, y: 16, opacity: 0 }}
            animate={{ scale: 1, y: 0, opacity: 1 }}
            exit={{ scale: 0.95, y: 10, opacity: 0 }}
            transition={{ type: "spring", stiffness: 320, damping: 28 }}
            onClick={(e) => e.stopPropagation()}
            className="relative bg-surface border-2 border-border rounded-3xl p-8 max-w-md w-full shadow-[0_20px_60px_-15px_rgba(0,0,0,0.9)]"
          >
            <button
              onClick={handleCancel}
              className="absolute top-4 right-4 text-muted hover:text-text transition-colors"
              aria-label="Закрыть"
            >
              <X size={18} />
            </button>

            <div className="flex items-start gap-4 mb-6">
              <div className="shrink-0 w-12 h-12 rounded-2xl bg-accent/15 border border-accent/40 flex items-center justify-center text-accent">
                <AlertTriangle size={22} />
              </div>
              <div>
                <h2 className="text-xl font-display font-bold text-text mb-2">
                  {data?.title || "Подтверди действие"}
                </h2>
                {data?.message && (
                  <p className="text-sm text-muted leading-relaxed">
                    {data.message}
                  </p>
                )}
              </div>
            </div>

            <div className="flex gap-3 justify-end">
              <Button
                variant="ghost"
                onClick={handleCancel}
                className="text-muted hover:text-text"
              >
                {data?.cancelLabel || "Отмена"}
              </Button>
              <Button
                variant={data?.danger ? "danger" : "primary"}
                onClick={handleConfirm}
              >
                {data?.confirmLabel || "Да, продолжить"}
              </Button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
