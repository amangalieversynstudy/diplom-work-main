import { useState } from "react";
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
  const dict = useDictionary();
  const copy = dict.auth.login;

  async function onSubmit(e) {
    e.preventDefault();
    setLoading(true);
    try {
      await login({ email: identifier, username: identifier, password });
      toast.success(copy.success);
      window.location.href = "/";
    } catch (err) {
      const msg = err?.response?.data?.detail || copy.error;
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Layout>
      <div className="max-w-md mx-auto">
        <Card tone="night" title={copy.title} subtitle={copy.subtitle}>
          <form className="flex flex-col gap-4" onSubmit={onSubmit}>
            <label className="text-sm text-white/70">
              {copy.identifierLabel}
              <input
                className="mt-1 w-full bg-white/5 border border-white/15 rounded-2xl px-4 py-2"
                placeholder={copy.identifierPlaceholder}
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
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
