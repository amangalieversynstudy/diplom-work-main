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

import { useEffect, useId, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { AlertTriangle, X } from "lucide-react";
import Button from "./Button";
import { useI18n } from "../lib/i18n";

export default function ConfirmModal({ data, onClose }) {
  const { t } = useI18n();
  const open = Boolean(data);
  const dialogRef = useRef(null);
  const titleId = useId();
  // onClose приходит новым замыканием на каждый рендер родителя; в зависимостях
  // эффекта он сбрасывал бы фокус при каждой перерисовке.
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  // Диалог: фокус внутрь (на «Отмена»), Tab не выходит за пределы окна,
  // Esc закрывает, при закрытии фокус возвращается на то, что было в фокусе.
  useEffect(() => {
    if (!open) return undefined;
    const previous = document.activeElement;
    const focusable = () =>
      dialogRef.current
        ? [
            ...dialogRef.current.querySelectorAll(
              'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
            ),
          ].filter((el) => !el.disabled)
        : [];
    const timer = setTimeout(() => {
      const items = focusable();
      (items.find((el) => el.dataset.autofocus !== undefined) || items[0])?.focus();
    }, 0);
    const onKey = (e) => {
      if (e.key === "Escape") {
        onCloseRef.current?.();
        return;
      }
      if (e.key !== "Tab") return;
      const items = focusable();
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      clearTimeout(timer);
      window.removeEventListener("keydown", onKey);
      previous?.focus?.();
    };
  }, [open]);

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
          className="fixed inset-0 z-[1000] flex items-center justify-center bg-modal-overlay backdrop-blur-sm px-4"
        >
          <motion.div
            ref={dialogRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            initial={{ scale: 0.92, y: 16, opacity: 0 }}
            animate={{ scale: 1, y: 0, opacity: 1 }}
            exit={{ scale: 0.95, y: 10, opacity: 0 }}
            transition={{ type: "spring", stiffness: 320, damping: 28 }}
            onClick={(e) => e.stopPropagation()}
            className="relative bg-modal-bg text-modal-text border-2 border-card-border rounded-3xl p-8 max-w-md w-full shadow-[0_20px_60px_-15px_rgba(0,0,0,0.45)] dark:shadow-[0_20px_60px_-15px_rgba(0,0,0,0.9)]"
          >
            <button
              onClick={handleCancel}
              className="absolute top-4 right-4 text-card-muted hover:text-modal-text transition-colors"
              aria-label={t("confirm.close")}
            >
              <X size={18} />
            </button>

            <div className="flex items-start gap-4 mb-6">
              <div className="shrink-0 w-12 h-12 rounded-2xl bg-accent/15 border border-accent/40 flex items-center justify-center text-accent">
                <AlertTriangle size={22} />
              </div>
              <div>
                <h2 id={titleId} className="text-xl font-display font-bold text-modal-text mb-2">
                  {data?.title || t("confirm.title")}
                </h2>
                {data?.message && (
                  <p className="text-sm text-card-muted leading-relaxed">
                    {data.message}
                  </p>
                )}
              </div>
            </div>

            <div className="flex gap-3 justify-end">
              <Button
                variant="ghost"
                data-autofocus
                onClick={handleCancel}
                className="text-card-muted hover:text-modal-text"
              >
                {data?.cancelLabel || t("confirm.cancel")}
              </Button>
              <Button
                variant={data?.danger ? "danger" : "primary"}
                onClick={handleConfirm}
              >
                {data?.confirmLabel || t("confirm.ok")}
              </Button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
