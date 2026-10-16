import { useState } from "react";
import { useRouter } from "next/router";
import Layout from "../components/Layout";
import Card from "../components/Card";
import AuthGate from "../components/AuthGate";
import Button from "../components/Button";
import PasswordInput from "../components/PasswordInput";
import { toast } from "sonner";
import { registerUser, login as loginUser } from "../lib/api";
import { useDictionary } from "../lib/i18n";
import { clearPlayerClass } from "../lib/class";
import { markOnboardingPending } from "../lib/onboarding";
import { homePathFor } from "../lib/roles";
import { pathAfterAuth, takeJoinCode } from "../lib/join";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function Register() {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [role, setRole] = useState("student");
  // код приглашения нужен, только если владелец выключил свободную регистрацию преподавателей
  const [needCode, setNeedCode] = useState(false);
  const [teacherCode, setTeacherCode] = useState("");
  const [researchConsent, setResearchConsent] = useState(false);
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const dict = useDictionary();
  const copy = dict.auth.register;
  const extra = dict.auth.registerExtra || {};
  const toggle = dict.auth.passwordToggle || {};
  const router = useRouter();

  function validate() {
    const e = {};
    if (!username.trim())
      e.username = copy.errUsername || "Придумай имя пользователя";
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
      await registerUser({
        username,
        email: trimmedEmail,
        password,
        role,
        teacher_code: role === "teacher" && needCode ? teacherCode.trim() : "",
        research_consent: researchConsent,
      });

      clearPlayerClass();
      if (role === "student") markOnboardingPending();

      if (trimmedEmail) {
        // Email указан → аккаунт is_active=False до подтверждения по ссылке.
        // Авто-логин делать НЕЛЬЗЯ — он вернёт 401 "No active account".
        toast.success(
          dict.auth.registerExtra?.successWithEmail ||
            "Аккаунт создан! Проверь почту — мы отправили ссылку для активации."
        );
        router.push(`/login?pending_verify=${encodeURIComponent(trimmedEmail)}`);
      } else {
        // Email не указан → аккаунт активен сразу: входим за человека и ведём к делу,
        // а не заставляем второй раз вводить только что придуманные логин и пароль.
        toast.success(copy.success);
        try {
          await loginUser({ email: username, username, password });
          const toJoin = role === "student" ? takeJoinCode() : "";
          router.push(pathAfterAuth(role === "teacher" ? homePathFor({ is_teacher: true }) : "/worlds", toJoin));
        } catch {
          router.push("/login");
        }
      }
    } catch (err) {
      const detail = err?.response?.data || {};
      // Разложим ошибки бэкенда по полям, если они пришли структурой.
      const fieldErrors = {};
      ["username", "email", "password", "teacher_code", "role"].forEach((k) => {
        if (detail[k])
          fieldErrors[k] = Array.isArray(detail[k]) ? detail[k][0] : detail[k];
      });
      // Свободная регистрация преподавателей выключена или код неверен: просим код приглашения.
      if (detail.teacher_code || detail.role) setNeedCode(true);
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
      <span role="alert" className="mt-1 block text-xs text-error">{errors[k]}</span>
    ) : null;

  return (
    <Layout>
      <div className="max-w-md mx-auto mt-24 mb-10">
        <AuthGate />
        <Card variant="scroll" title={copy.title} subtitle={copy.subtitle}>
          <form className="flex flex-col gap-4" onSubmit={onSubmit} noValidate>
            <fieldset>
              <legend className="text-sm text-muted mb-1">{extra.roleLabel || "Кто ты?"}</legend>
              <div className="grid grid-cols-2 gap-2" role="group" aria-label={extra.roleLabel || "Кто ты?"}>
                {[
                  ["student", extra.roleStudent || "Я ученик"],
                  ["teacher", extra.roleTeacher || "Я преподаватель"],
                ].map(([value, label]) => (
                  <button
                    key={value}
                    type="button"
                    aria-pressed={role === value}
                    onClick={() => {
                      setRole(value);
                      clearError("role");
                    }}
                    className={`min-h-[44px] rounded-2xl border px-3 py-2 text-sm font-semibold transition-colors ${
                      role === value
                        ? "border-primary bg-primary text-on-primary"
                        : "border-border bg-panel text-text hover:border-primary"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <p className="mt-2 text-xs text-muted">
                {role === "teacher"
                  ? extra.roleTeacherHint || "Кабинет, аналитика и студия курсов. Ты видишь только учеников своих курсов."
                  : extra.roleStudentHint || "Проходи миссии, получай опыт и смотри свой путь."}
              </p>
            </fieldset>
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
              <span className="mt-1 block text-xs text-muted">{copy.usernameHint}</span>
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
              {copy.confirmLabel || "Повтори пароль"}
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

            {role === "teacher" && needCode ? (
              <label className="text-sm text-muted">
                {extra.teacherCodeLabel || "Код преподавателя"}
                <input
                  className={inputCls("teacher_code")}
                  placeholder={extra.teacherCodePlaceholder || "Код, выданный администратором"}
                  value={teacherCode}
                  onChange={(e) => {
                    setTeacherCode(e.target.value);
                    clearError("teacher_code");
                    clearError("role");
                  }}
                />
                <FieldError k="teacher_code" />
                <FieldError k="role" />
              </label>
            ) : null}

            <label className="flex items-start gap-3 text-sm text-muted cursor-pointer">
              <input
                type="checkbox"
                className="mt-1 h-4 w-4 shrink-0 accent-[var(--primary)]"
                checked={researchConsent}
                onChange={(e) => setResearchConsent(e.target.checked)}
              />
              <span>
                {extra.researchConsent}
                <span className="block text-xs text-faint mt-1">
                  {extra.researchConsentHint}
                </span>
              </span>
            </label>

            <Button variant="rune" type="submit" disabled={loading}>
              {loading ? copy.submitting : copy.submit}
            </Button>
          </form>
          <p className="text-xs text-faint mt-3">{copy.helper}</p>
        </Card>
      </div>
    </Layout>
  );
}
