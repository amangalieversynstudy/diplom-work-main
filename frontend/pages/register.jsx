import { useState } from "react";
import Layout from "../components/Layout";
import Card from "../components/Card";
import Button from "../components/Button";
import { toast } from "sonner";
import { registerUser } from "../lib/api";
import { useDictionary } from "../lib/i18n";

export default function Register() {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const dict = useDictionary();
  const copy = dict.auth.register;

  async function onSubmit(e) {
    e.preventDefault();
    setLoading(true);
    try {
      await registerUser({ username, email, password });
      toast.success(copy.success);
      window.location.href = "/login";
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
      <div className="max-w-md mx-auto">
        <Card tone="aurora" title={copy.title} subtitle={copy.subtitle}>
          <form className="flex flex-col gap-4" onSubmit={onSubmit}>
            <label className="text-sm text-white/70">
              {copy.usernameLabel}
              <input
                className="mt-1 w-full bg-white/5 border border-white/15 rounded-2xl px-4 py-2"
                placeholder={copy.usernamePlaceholder}
                value={username}
                onChange={(e) => setUsername(e.target.value)}
              />
            </label>
            <label className="text-sm text-white/70">
              {copy.emailLabel}
              <input
                className="mt-1 w-full bg-white/5 border border-white/15 rounded-2xl px-4 py-2"
                placeholder={copy.emailPlaceholder}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </label>
            <label className="text-sm text-white/70">
              {copy.passwordLabel}
              <input
                className="mt-1 w-full bg-white/5 border border-white/15 rounded-2xl px-4 py-2"
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
          <p className="text-xs text-white/50 mt-3">{copy.helper}</p>
        </Card>
      </div>
    </Layout>
  );
}
