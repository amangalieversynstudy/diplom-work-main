import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import Link from "next/link";
import Layout from "../components/Layout";
import Card from "../components/Card";
import Button from "../components/Button";
import PasswordInput from "../components/PasswordInput";
import { toast } from "sonner";
import { Auth } from "../lib/api";
import { useDictionary } from "../lib/i18n";

/**
 * Страница задаёт новый пароль по ссылке из письма
 *   {FRONTEND_URL}/reset-password-confirm?uid=<base64>&token=<token>
 * и шлёт POST /api/auth/password-reset-confirm/.
 */
export default function ResetPasswordConfirm() {
  const router = useRouter();
  const dict = useDictionary();
  const copy = dict.auth.reset || {};
  const toggle = dict.auth.passwordToggle || {};

  const [uid, setUid] = useState("");
  const [token, setToken] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [badLink, setBadLink] = useState(false);

  useEffect(() => {
    if (!router.isReady) return;
    const u = router.query.uid;
    const t = router.query.token;
    if (!u || !t) {
      setBadLink(true);
      return;
    }
    setUid(String(u));
    setToken(String(t));
  }, [router.isReady, router.query]);

  function validate() {
    const e = {};
    if (password.length < 8)
      e.password = copy.errShort || "Пароль должен быть не короче 8 символов";
    if (confirm !== password)
      e.confirm = copy.errMismatch || "Пароли не совпадают";
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  const clearError = (key) =>
    setErrors((p) => (p[key] ? { ...p, [key]: undefined } : p));

  async function onSubmit(e) {
    e.preventDefault();
    if (!validate()) return;
    setLoading(true);
    try {
      await Auth.confirmPasswordReset({ uid, token, new_password: password });
      toast.success(copy.success || "Пароль обновлён! Войди с новым паролем.");
      router.push("/login");
    } catch (err) {
      const detail =
        err?.response?.data?.detail ||
        (Array.isArray(err?.response?.data?.non_field_errors)
          ? err.response.data.non_field_errors[0]
          : "") ||
        copy.invalid ||
        "Ссылка недействительна или устарела. Запроси сброс заново.";
      toast.error(detail);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Layout>
      <div className="max-w-md mx-auto mt-24 mb-10">
        <Card
          title={copy.title || "Новый пароль"}
          subtitle={copy.subtitle || "Придумай новый пароль для входа"}
        >
          {badLink ? (
            <div className="text-center py-4">
              <p className="text-muted text-sm mb-6">
                {copy.badLink ||
                  "Ссылка повреждена: отсутствует uid или token. Запроси сброс пароля заново."}
              </p>
              <Link
                href="/forgot-password"
                className="font-semibold text-primary hover:text-primary-dk transition-colors text-sm"
              >
                {copy.requestAgain || "Запросить ссылку заново"}
              </Link>
            </div>
          ) : (
            <form className="flex flex-col gap-4" onSubmit={onSubmit} noValidate>
              <label className="text-sm text-muted">
                {copy.passwordLabel || "Новый пароль"}
                <PasswordInput
                  value={password}
                  autoComplete="new-password"
                  placeholder={copy.passwordPlaceholder || "••••••••"}
                  invalid={!!errors.password}
                  showLabel={toggle.show}
                  hideLabel={toggle.hide}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    clearError("password");
                  }}
                />
                {errors.password && (
                  <span className="mt-1 block text-xs text-red-400">
                    {errors.password}
                  </span>
                )}
              </label>
              <label className="text-sm text-muted">
                {copy.confirmLabel || "Повторите пароль"}
                <PasswordInput
                  value={confirm}
                  autoComplete="new-password"
                  placeholder={copy.confirmPlaceholder || "••••••••"}
                  invalid={!!errors.confirm}
                  showLabel={toggle.show}
                  hideLabel={toggle.hide}
                  onChange={(e) => {
                    setConfirm(e.target.value);
                    clearError("confirm");
                  }}
                />
                {errors.confirm && (
                  <span className="mt-1 block text-xs text-red-400">
                    {errors.confirm}
                  </span>
                )}
              </label>
              <Button type="submit" disabled={loading}>
                {loading
                  ? copy.submitting || "Сохраняем…"
                  : copy.submit || "Сохранить пароль"}
              </Button>
            </form>
          )}
        </Card>
      </div>
    </Layout>
  );
}
