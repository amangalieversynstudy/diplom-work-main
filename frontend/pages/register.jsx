import { useState } from "react";
import { useRouter } from "next/router";
import Layout from "../components/Layout";
import Card from "../components/Card";
import Button from "../components/Button";
import { toast } from "sonner";
import { registerUser } from "../lib/api";
import { useDictionary } from "../lib/i18n";
import { clearPlayerClass } from "../lib/class"; // <--- Импортируем нашу новую функцию

export default function Register() {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const dict = useDictionary();
  const copy = dict.auth.register;
  const router = useRouter();

  async function onSubmit(e) {
    e.preventDefault();
    setLoading(true);
    try {
      await registerUser({ username, email, password });

      // Аккаунт создан, но is_active=False до подтверждения email.
      // Авто-логин делать НЕЛЬЗЯ — он вернёт 401 "No active account".
      clearPlayerClass();

      toast.success(
        dict.auth.registerExtra?.successWithEmail ||
          "Аккаунт создан! Проверь почту — мы отправили ссылку для активации."
      );
      router.push(`/login?pending_verify=${encodeURIComponent(email)}`);
    } catch (err) {
      const detail = err?.response?.data || {};
      const msg =
        detail.detail ||
        Object.values(detail)
          .flat()
          .join(", ") ||
        copy.error;
      toast.error(msg || copy.error);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Layout>
      <div className="max-w-md mx-auto mt-24 mb-10">
        <Card title={copy.title} subtitle={copy.subtitle}>
          <form className="flex flex-col gap-4" onSubmit={onSubmit}>
            <label className="text-sm text-muted">
              {copy.usernameLabel}
              <input
                className="mt-1 w-full bg-panel border border-border text-text placeholder:text-faint rounded-2xl px-4 py-2 focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/30 transition-all"
                placeholder={copy.usernamePlaceholder}
                value={username}
                onChange={(e) => setUsername(e.target.value)}
              />
            </label>
            <label className="text-sm text-muted">
              {copy.emailLabel}
              <input
                className="mt-1 w-full bg-panel border border-border text-text placeholder:text-faint rounded-2xl px-4 py-2 focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/30 transition-all"
                placeholder={copy.emailPlaceholder}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
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
