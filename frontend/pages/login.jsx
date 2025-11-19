import { useState } from "react";
import Layout from "../components/Layout";
import Card from "../components/Card";
import Button from "../components/Button";
import { toast } from "sonner";
import { login } from "../lib/api";

export default function Login() {
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    setLoading(true);
    try {
      await login({ email: identifier, username: identifier, password });
      toast.success("Signed in");
      window.location.href = "/";
    } catch (err) {
      const msg = err?.response?.data?.detail || "Login failed";
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Layout>
      <div className="max-w-md mx-auto">
        <Card tone="night" title="Gate Access" subtitle="Authenticate to continue">
          <form className="flex flex-col gap-4" onSubmit={onSubmit}>
            <label className="text-sm text-white/70">
              Identifier
              <input
                className="mt-1 w-full bg-white/5 border border-white/15 rounded-2xl px-4 py-2"
                placeholder="Email or username"
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
              />
            </label>
            <label className="text-sm text-white/70">
              Password
              <input
                className="mt-1 w-full bg-white/5 border border-white/15 rounded-2xl px-4 py-2"
                placeholder="••••••••"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </label>
            <Button type="submit" disabled={loading}>
              {loading ? "Signing in…" : "Sign in"}
            </Button>
          </form>
          <p className="text-xs text-white/50 mt-3">
            Tokens stored client-side; use /auth endpoints on backend for production flows.
          </p>
        </Card>
      </div>
    </Layout>
  );
}
