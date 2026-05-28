import { useState, useEffect } from "react";
import { useRouter } from "next/router";
import Link from "next/link";
import Layout from "../components/Layout";
import Card from "../components/Card";
import Button from "../components/Button";
import { toast } from "sonner";
import { login, Profile as ProfileAPI } from "../lib/api";
import { useDictionary } from "../lib/i18n";

export default function Login() {
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [pendingEmail, setPendingEmail] = useState("");
  const dict = useDictionary();
  const copy = dict.auth.login;
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

  async function onSubmit(e) {
    e.preventDefault();

    if (!identifier || !password) {
      toast.error(copy.fillAll || "Заполните все поля", { duration: 4000 });
      return;
    }

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
      const detail = err?.response?.data?.detail || "";
      if (detail.toLowerCase().includes("no active account")) {
        toast.error(copy.notActivated || "Account not activated. Check your email.", {
          duration: 5000,
        });
      } else {
        toast.error(detail || copy.error || "Login failed", { duration: 5000 });
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <Layout>
      <div className="max-w-md mx-auto mt-24 mb-10">
        <Card title={copy.title} subtitle={copy.subtitle}>
          {pendingEmail && (
            <div className="mb-4 rounded-2xl border border-primary/30 bg-primary/10 px-4 py-3 text-sm text-text">
              <p className="font-semibold mb-1">📜 {copy.emailSentTitle || "Письмо отправлено"}</p>
              <p className="text-muted text-xs">
                {(copy.emailSentBody || "Мы отправили ссылку для активации на {email}.")
                  .split("{email}")
                  .map((chunk, idx, arr) => (
                    <span key={idx}>
                      {chunk}
                      {idx < arr.length - 1 && <b>{pendingEmail}</b>}
                    </span>
                  ))}
              </p>
            </div>
          )}
          <form className="flex flex-col gap-4" onSubmit={onSubmit}>
            <label className="text-sm text-muted">
              {copy.identifierLabel}
              <input
                className="mt-1 w-full bg-panel border border-border text-text placeholder:text-faint rounded-2xl px-4 py-2 focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/30 transition-all"
                placeholder={copy.identifierPlaceholder}
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
              />
            </label>
            <label className="text-sm text-muted">
              {copy.passwordLabel}
              <input
                className="mt-1 w-full bg-panel border border-border text-text placeholder:text-faint rounded-2xl px-4 py-2 focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/30 transition-all"
                placeholder={copy.passwordPlaceholder}
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
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