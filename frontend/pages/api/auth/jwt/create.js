export default function handler(req, res) {
  if (req.method !== "POST")
    return res.status(405).json({ detail: "Method not allowed" });
  const { email, password } = req.body || {};
  if (email && password) {
    // Demo tokens (do NOT use in production)
    return res
      .status(200)
      .json({ access: "demo-access-token", refresh: "demo-refresh-token" });
  }
  return res.status(400).json({ detail: "Invalid credentials" });
}
