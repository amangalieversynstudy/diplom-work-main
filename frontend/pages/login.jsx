import { useState, useEffect } from "react";
import { useRouter } from "next/router";
import Layout from "../components/Layout";
import Card from "../components/Card";
import Button from "../components/Button";
import { toast } from "sonner";
import { login } from "../lib/api";
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
    setLoading(true);
    try {
      await login({ email: identifier, username: identifier, password });
      toast.success(copy.success || "Добро пожаловать!");
      window.location.href = "/profile";
    } catch (err) {
      const detail = err?.response?.data?.detail || "";
      // Специальное сообщение для неактивированного аккаунта
      if (detail.toLowerCase().includes("no active account")) {
        toast.error(
          "Аккаунт не активирован. Проверь почту и перейди по ссылке в письме."
        );
      } else {
        toast.error(detail || copy.error || "Ошибка входа");
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
              <p className="font-semibold mb-1">📜 Письмо отправлено</p>
              <p className="text-muted text-xs">
                Мы отправили ссылку для активации на <b>{pendingEmail}</b>.
                В DEBUG-режиме аккаунт уже активен — можешь логиниться сразу.
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
          <p className="text-xs text-faint mt-3">{copy.helper}</p>
        </Card>
      </div>
    </Layout>
  );
}
