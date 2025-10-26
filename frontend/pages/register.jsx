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
        <Card title="Create account" subtitle="Join RPG Academy">
          <form className="flex flex-col gap-3" onSubmit={onSubmit}>
            <input
              className="bg-white/10 border border-white/10 rounded px-3 py-2"
              placeholder="Username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
            <input
              className="bg-white/10 border border-white/10 rounded px-3 py-2"
              placeholder="Email (optional)"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <input
              className="bg-white/10 border border-white/10 rounded px-3 py-2"
              placeholder="Password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <Button type="submit" disabled={loading}>
              {loading ? "Creating…" : "Create account"}
            </Button>
          </form>
        </Card>
      </div>
    </Layout>
  );
}
