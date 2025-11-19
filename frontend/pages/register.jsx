import { useState } from "react";
import Layout from "../components/Layout";
import Card from "../components/Card";
import Button from "../components/Button";
import { toast } from "sonner";
import { registerUser } from "../lib/api";

export default function Register() {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    setLoading(true);
    try {
      await registerUser({ username, email, password });
      toast.success("Account created, please sign in");
      window.location.href = "/login";
    } catch (err) {
      const detail = err?.response?.data || {};
      const msg =
        detail.detail ||
        Object.values(detail).flat().join(", ") ||
        "Registration failed";
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Layout>
      <div className="max-w-md mx-auto">
        <Card tone="aurora" title="Join the Guild" subtitle="Provision new hero">
          <form className="flex flex-col gap-4" onSubmit={onSubmit}>
            <label className="text-sm text-white/70">
              Username
              <input
                className="mt-1 w-full bg-white/5 border border-white/15 rounded-2xl px-4 py-2"
                placeholder="adventurer"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
              />
            </label>
            <label className="text-sm text-white/70">
              Email (optional)
              <input
                className="mt-1 w-full bg-white/5 border border-white/15 rounded-2xl px-4 py-2"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
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
              {loading ? "Creating…" : "Create account"}
            </Button>
          </form>
          <p className="text-xs text-white/50 mt-3">
            Registration hits `/auth/register/` on the backend service; e-mail remains optional for
            demo environments.
          </p>
        </Card>
      </div>
    </Layout>
  );
}
