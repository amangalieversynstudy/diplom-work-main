export default function handler(req, res) {
  if (req.method !== "POST")
    return res.status(405).json({ detail: "Method not allowed" });
  return res.status(200).json({ status: "completed", xp_awarded: 50 });
}
