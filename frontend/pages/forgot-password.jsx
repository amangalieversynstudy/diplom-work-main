import { useState } from "react";
import Link from "next/link";
import Layout from "../components/Layout";
import Card from "../components/Card";
import Button from "../components/Button";
import { toast } from "sonner";
import { Mail, CheckCircle2 } from "lucide-react";
import { Auth } from "../lib/api";
import { useDictionary } from "../lib/i18n";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const dict = useDictionary();
  const copy = dict.auth.forgot || {};

  async function onSubmit(e) {
    e.preventDefault();
    const trimmed = email.trim();
    if (!EMAIL_RE.test(trimmed)) {
      setError(copy.errEmail || "Неверный формат e-mail");
      return;
    }
    setError("");
    setLoading(true);
    try {
      await Auth.requestPasswordReset(trimmed);
      // Ответ бэкенда намеренно обезличен — просто показываем «отправлено».
      setSent(true);
    } catch {
      toast.error(copy.error || "Что-то пошло не так. Попробуй позже.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Layout>
      <div className="max-w-md mx-auto mt-24 mb-10">
        <Card
          title={copy.title || "Восстановление доступа"}
          subtitle={copy.subtitle || "Пришлём ссылку для сброса пароля"}
        >
          {sent ? (
            <div className="text-center py-4">
              <div className="grid h-16 w-16 mx-auto place-items-center rounded-2xl bg-emerald-400/10 border border-emerald-400/20 mb-5">
                <CheckCircle2 size={30} className="text-emerald-400" />
              </div>
              <p className="text-text font-semibold mb-2">
                {copy.sentTitle || "Проверь почту"}
              </p>
              <p className="text-muted text-sm mb-6">
                {copy.sent ||
                  "Если такой email зарегистрирован, мы отправили на него ссылку для сброса пароля."}
              </p>
              <Link
                href="/login"
                className="font-semibold text-primary hover:text-primary-dk transition-colors text-sm"
              >
                {copy.backToLogin || "← Вернуться ко входу"}
              </Link>
            </div>
          ) : (
            <>
              <form className="flex flex-col gap-4" onSubmit={onSubmit} noValidate>
                <label className="text-sm text-muted">
                  {copy.emailLabel || "E-mail"}
                  <div className="relative mt-1">
                    <Mail
                      size={18}
                      className="absolute left-3 top-1/2 -translate-y-1/2 text-muted pointer-events-none"
                    />
                    <input
                      type="email"
                      className={`w-full bg-panel border text-text placeholder:text-faint rounded-2xl pl-10 pr-4 py-2 focus:outline-none focus:ring-1 transition-all ${
                        error
                          ? "border-red-500/60 focus:border-red-500 focus:ring-red-500/30"
                          : "border-border focus:border-primary focus:ring-primary/30"
                      }`}
                      placeholder={copy.emailPlaceholder || "you@example.com"}
                      value={email}
                      onChange={(e) => {
                        setEmail(e.target.value);
                        if (error) setError("");
                      }}
                    />
                  </div>
                  {error && (
                    <span className="mt-1 block text-xs text-red-400">{error}</span>
                  )}
                </label>
                <Button type="submit" disabled={loading}>
                  {loading
                    ? copy.submitting || "Отправляем…"
                    : copy.submit || "Отправить ссылку"}
                </Button>
              </form>
              <p className="text-xs text-card-muted mt-3">
                {copy.helper ||
                  "Укажи e-mail, привязанный к аккаунту — пришлём на него ссылку."}
              </p>
              <div className="mt-5 pt-4 border-t border-card-border text-sm text-card-muted text-center">
                <Link
                  href="/login"
                  className="font-semibold text-primary hover:text-primary-dk transition-colors"
                >
                  {copy.backToLogin || "← Вернуться ко входу"}
                </Link>
              </div>
            </>
          )}
        </Card>
      </div>
    </Layout>
  );
}
