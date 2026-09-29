import { useEffect, useRef } from "react";

/**
 * Поведение модального окна для клавиатуры и скринридера: фокус уходит внутрь
 * (на элемент с data-autofocus или на первый), Tab не выходит за пределы окна,
 * Esc закрывает, а при закрытии фокус возвращается туда, где он был.
 */
export function useDialog(open, dialogRef, onClose) {
  // onClose приходит новым замыканием на каждый рендер родителя; в зависимостях
  // эффекта он сбрасывал бы фокус при каждой перерисовке.
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

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
  }, [open, dialogRef]);
}
