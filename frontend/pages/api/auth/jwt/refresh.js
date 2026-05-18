export default function handler(req, res) {
  if (req.method !== "POST")
    return res.status(405).json({ detail: "Method not allowed" });
  const { refresh } = req.body || {};
  if (refresh) {
    return res.status(200).json({ access: "demo-access-token-refreshed" });
  }
  return res.status(400).json({ detail: "Invalid refresh token" });
}
