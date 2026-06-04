import { useState, useEffect } from "react";
import { useRouter } from "next/router";
import Link from "next/link";
import Layout from "../components/Layout";
import Card from "../components/Card";
import Button from "../components/Button";
import PasswordInput from "../components/PasswordInput";
import { toast } from "sonner";
import { login, Auth, Profile as ProfileAPI } from "../lib/api";
import { useDictionary } from "../lib/i18n";

export default function Login() {
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [pendingEmail, setPendingEmail] = useState("");
  const [errors, setErrors] = useState({});
  const [showResend, setShowResend] = useState(false);
  const [resending, setResending] = useState(false);
  const dict = useDictionary();
  const copy = dict.auth.login;
  const toggle = dict.auth.passwordToggle || {};
  const router = useRouter();

  // После регистрации фронт редиректит сюда с ?pending_verify=email
  // Показываем подсказку о необходимости активации.
  useEffect(() => {
    if (router.query.pending_verify) {
      const email = String(router.query.pending_verify);
      setPendingEmail(email);
      setIdentifier(email);
    }
  }, [router.query.pending_verify]);

  function validate() {
    const e = {};
    if (!identifier.trim())
      e.identifier = copy.errorIdentifier || "Укажите логин или e-mail";
    if (!password) e.password = copy.errorPassword || "Введите пароль";
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function onSubmit(e) {
    e.preventDefault();
    if (!validate()) return;

    setLoading(true);
    try {
      await login({ email: identifier, username: identifier, password });
      toast.success(copy.success || "Welcome!", { duration: 2000 });

      // Smart redirect: newcomer → class picker, returning user → worlds
      const userData = await ProfileAPI.me();
      if (!userData?.profile?.class_role && !userData?.class_role) {
        router.push("/class");
      } else {
        router.push("/worlds");
      }
    } catch (err) {
      const data = err?.response?.data || {};
      const detail = data.detail || "";
      // Бэк отдаёт code:"account_inactive" для неактивного аккаунта — надёжно
      // и не зависит от локали. Строковый матч оставлен fallback'ом на случай
      // старого бэка / гонки деплоя Vercel↔Railway.
      const inactive =
        data.code === "account_inactive" ||
        detail.toLowerCase().includes("no active account");
      if (inactive) {
        setShowResend(true);
        toast.error(
          copy.notActivated || "Account not activated. Check your email.",
          { duration: 5000 }
        );
      } else {
        toast.error(detail || copy.error || "Login failed", { duration: 5000 });
      }
    } finally {
      setLoading(false);
    }
  }

  async function onResend() {
    const email = identifier.trim();
    if (!email || !email.includes("@")) {
      toast.error(copy.resendNeedsEmail || "Введите e-mail, на который пришлёт письмо.");
      return;
    }
    setResending(true);
    try {
      await Auth.resendVerification(email);
      toast.success(
        copy.resendSent || "Письмо отправлено повторно. Проверь почту."
      );
    } catch {
      toast.error(copy.error || "Ошибка");
    } finally {
      setResending(false);
    }
  }

  return (
    <Layout>
      <div className="max-w-md mx-auto mt-24 mb-10">
        <Card title={copy.title} subtitle={copy.subtitle}>
          {(pendingEmail || showResend) && (
            <div className="mb-4 rounded-2xl border border-primary/30 bg-primary/10 px-4 py-3 text-sm text-text">
              <p className="font-semibold mb-1">
                📜 {copy.emailSentTitle || "Письмо отправлено"}
              </p>
              {pendingEmail ? (
                <p className="text-muted text-xs mb-2">
                  {(copy.emailSentBody ||
                    "Мы отправили ссылку для активации на {email}.")
                    .split("{email}")
                    .map((chunk, idx, arr) => (
                      <span key={idx}>
                        {chunk}
                        {idx < arr.length - 1 && <b>{pendingEmail}</b>}
                      </span>
                    ))}
                </p>
              ) : (
                <p className="text-muted text-xs mb-2">
                  {copy.notActivated ||
                    "Аккаунт не активирован. Проверь почту и перейди по ссылке."}
                </p>
              )}
              <button
                type="button"
                onClick={onResend}
                disabled={resending}
                className="text-xs font-semibold text-primary hover:text-primary-dk transition-colors disabled:opacity-50"
              >
                {resending
                  ? copy.resending || "Отправляем…"
                  : copy.resend || "Отправить письмо повторно"}
              </button>
            </div>
          )}
          <form className="flex flex-col gap-4" onSubmit={onSubmit} noValidate>
            <label className="text-sm text-muted">
              {copy.identifierLabel}
              <input
                className={`mt-1 w-full bg-panel border text-text placeholder:text-faint rounded-2xl px-4 py-2 focus:outline-none focus:ring-1 transition-all ${
                  errors.identifier
                    ? "border-red-500/60 focus:border-red-500 focus:ring-red-500/30"
                    : "border-border focus:border-primary focus:ring-primary/30"
                }`}
                placeholder={copy.identifierPlaceholder}
                value={identifier}
                onChange={(e) => {
                  setIdentifier(e.target.value);
                  if (errors.identifier)
                    setErrors((p) => ({ ...p, identifier: undefined }));
                }}
              />
              {errors.identifier && (
                <span className="mt-1 block text-xs text-red-400">
                  {errors.identifier}
                </span>
              )}
            </label>
            <label className="text-sm text-muted">
              <span className="flex items-center justify-between">
                {copy.passwordLabel}
                <Link
                  href="/forgot-password"
                  className="text-xs font-semibold text-primary hover:text-primary-dk transition-colors"
                >
                  {copy.forgotPassword || "Забыли пароль?"}
                </Link>
              </span>
              <PasswordInput
                value={password}
                autoComplete="current-password"
                placeholder={copy.passwordPlaceholder}
                invalid={!!errors.password}
                showLabel={toggle.show}
                hideLabel={toggle.hide}
                onChange={(e) => {
                  setPassword(e.target.value);
                  if (errors.password)
                    setErrors((p) => ({ ...p, password: undefined }));
                }}
              />
              {errors.password && (
                <span className="mt-1 block text-xs text-red-400">
                  {errors.password}
                </span>
              )}
            </label>
            <Button type="submit" disabled={loading}>
              {loading ? copy.submitting : copy.submit}
            </Button>
          </form>
          <p className="text-xs text-card-muted mt-3">{copy.helper}</p>
          <div className="mt-5 pt-4 border-t border-card-border text-sm text-card-muted text-center">
            {copy.noAccount || "Нет аккаунта?"}{" "}
            <Link
              href="/register"
              className="font-semibold text-primary hover:text-primary-dk transition-colors"
            >
              {copy.registerCta || "Регистрация →"}
            </Link>
          </div>
        </Card>
      </div>
    </Layout>
  );
}
