import { useState } from "react";
import { useRouter } from "next/router";
import Layout from "../components/Layout";
import Card from "../components/Card";
import Button from "../components/Button";
import PasswordInput from "../components/PasswordInput";
import { toast } from "sonner";
import { registerUser } from "../lib/api";
import { useDictionary } from "../lib/i18n";
import { clearPlayerClass } from "../lib/class"; // <--- Импортируем нашу новую функцию

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function Register() {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const dict = useDictionary();
  const copy = dict.auth.register;
  const toggle = dict.auth.passwordToggle || {};
  const router = useRouter();

  function validate() {
    const e = {};
    if (!username.trim())
      e.username = copy.errUsername || "Придумайте имя пользователя";
    const trimmedEmail = email.trim();
    if (trimmedEmail && !EMAIL_RE.test(trimmedEmail))
      e.email = copy.errEmail || "Неверный формат e-mail";
    if (password.length < 8)
      e.password = copy.errPasswordShort || "Пароль должен быть не короче 8 символов";
    if (confirm !== password)
      e.confirm = copy.errPasswordMismatch || "Пароли не совпадают";
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  const clearError = (key) =>
    setErrors((p) => (p[key] ? { ...p, [key]: undefined } : p));

  async function onSubmit(e) {
    e.preventDefault();
    if (!validate()) return;
    setLoading(true);
    const trimmedEmail = email.trim();
    try {
      await registerUser({ username, email: trimmedEmail, password });

      clearPlayerClass();

      if (trimmedEmail) {
        // Email указан → аккаунт is_active=False до подтверждения по ссылке.
        // Авто-логин делать НЕЛЬЗЯ — он вернёт 401 "No active account".
        toast.success(
          dict.auth.registerExtra?.successWithEmail ||
            "Аккаунт создан! Проверь почту — мы отправили ссылку для активации."
        );
        router.push(`/login?pending_verify=${encodeURIComponent(trimmedEmail)}`);
      } else {
        // Email не указан → аккаунт активируется сразу, ведём прямо ко входу.
        toast.success(copy.success);
        router.push("/login");
      }
    } catch (err) {
      const detail = err?.response?.data || {};
      // Разложим ошибки бэкенда по полям, если они пришли структурой.
      const fieldErrors = {};
      ["username", "email", "password"].forEach((k) => {
        if (detail[k])
          fieldErrors[k] = Array.isArray(detail[k]) ? detail[k][0] : detail[k];
      });
      if (Object.keys(fieldErrors).length) setErrors((p) => ({ ...p, ...fieldErrors }));
      const msg =
        detail.detail ||
        Object.values(detail).flat().join(", ") ||
        copy.error;
      toast.error(msg || copy.error);
    } finally {
      setLoading(false);
    }
  }

  const inputCls = (key) =>
    `mt-1 w-full bg-panel border text-text placeholder:text-faint rounded-2xl px-4 py-2 focus:outline-none focus:ring-1 transition-all ${
      errors[key]
        ? "border-red-500/60 focus:border-red-500 focus:ring-red-500/30"
        : "border-border focus:border-primary focus:ring-primary/30"
    }`;

  const FieldError = ({ k }) =>
    errors[k] ? (
      <span className="mt-1 block text-xs text-red-400">{errors[k]}</span>
    ) : null;

  return (
    <Layout>
      <div className="max-w-md mx-auto mt-24 mb-10">
        <Card title={copy.title} subtitle={copy.subtitle}>
          <form className="flex flex-col gap-4" onSubmit={onSubmit} noValidate>
            <label className="text-sm text-muted">
              {copy.usernameLabel}
              <input
                className={inputCls("username")}
                placeholder={copy.usernamePlaceholder}
                value={username}
                onChange={(e) => {
                  setUsername(e.target.value);
                  clearError("username");
                }}
              />
              <FieldError k="username" />
            </label>
            <label className="text-sm text-muted">
              {copy.emailLabel}
              <input
                className={inputCls("email")}
                placeholder={copy.emailPlaceholder}
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                  clearError("email");
                }}
              />
              <FieldError k="email" />
            </label>
            <label className="text-sm text-muted">
              {copy.passwordLabel}
              <PasswordInput
                value={password}
                autoComplete="new-password"
                placeholder={copy.passwordPlaceholder}
                invalid={!!errors.password}
                showLabel={toggle.show}
                hideLabel={toggle.hide}
                onChange={(e) => {
                  setPassword(e.target.value);
                  clearError("password");
                }}
              />
              <FieldError k="password" />
            </label>
            <label className="text-sm text-muted">
              {copy.confirmLabel || "Повторите пароль"}
              <PasswordInput
                value={confirm}
                autoComplete="new-password"
                placeholder={copy.confirmPlaceholder || copy.passwordPlaceholder}
                invalid={!!errors.confirm}
                showLabel={toggle.show}
                hideLabel={toggle.hide}
                onChange={(e) => {
                  setConfirm(e.target.value);
                  clearError("confirm");
                }}
              />
              <FieldError k="confirm" />
            </label>
            <Button type="submit" disabled={loading}>
              {loading ? copy.submitting : copy.submit}
            </Button>
          </form>
          <p className="text-xs text-faint mt-3">{copy.helper}</p>
        </Card>
      </div>
    </Layout>
  );
}
