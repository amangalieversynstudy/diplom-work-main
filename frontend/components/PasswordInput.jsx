import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";

/**
 * Поле ввода пароля с кнопкой «показать/скрыть».
 *
 * Полностью контролируемое: value/onChange приходят сверху. Стили совпадают
 * с обычными полями форм (см. login/register), плюс правый отступ под глаз.
 * Лейблы кнопки прокидываются через showLabel/hideLabel — для i18n.
 */
export default function PasswordInput({
  value,
  onChange,
  placeholder = "••••••••",
  autoComplete = "current-password",
  id,
  name,
  invalid = false,
  showLabel = "Показать пароль",
  hideLabel = "Скрыть пароль",
  onKeyDown,
}) {
  const [show, setShow] = useState(false);

  return (
    <div className="relative mt-1">
      <input
        id={id}
        name={name}
        type={show ? "text" : "password"}
        value={value}
        onChange={onChange}
        onKeyDown={onKeyDown}
        placeholder={placeholder}
        autoComplete={autoComplete}
        aria-invalid={invalid || undefined}
        className={`w-full bg-panel border text-text placeholder:text-faint rounded-2xl px-4 py-2 pr-11 focus:outline-none focus:ring-1 transition-all ${
          invalid
            ? "border-red-500/60 focus:border-red-500 focus:ring-red-500/30"
            : "border-border focus:border-primary focus:ring-primary/30"
        }`}
      />
      <button
        type="button"
        onClick={() => setShow((s) => !s)}
        tabIndex={-1}
        aria-label={show ? hideLabel : showLabel}
        title={show ? hideLabel : showLabel}
        className="absolute inset-y-0 right-0 grid w-11 place-items-center text-muted hover:text-text transition-colors"
      >
        {show ? <EyeOff size={18} /> : <Eye size={18} />}
      </button>
    </div>
  );
}
