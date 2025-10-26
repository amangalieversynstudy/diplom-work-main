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
        <Card title="Login" subtitle="Sign in to your account">
          <form className="flex flex-col gap-3" onSubmit={onSubmit}>
            <input
              className="bg-white/10 border border-white/10 rounded px-3 py-2"
              placeholder="Email or Username"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
            />
            <input
              className="bg-white/10 border border-white/10 rounded px-3 py-2"
              placeholder="Password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <Button type="submit" disabled={loading}>
              {loading ? "Signing in…" : "Sign in"}
            </Button>
          </form>
        </Card>
      </div>
    </Layout>
  );
}
