export default function handler(req, res) {
  if (req.method !== "GET")
    return res.status(405).json({ detail: "Method not allowed" });
  return res
    .status(200)
    .json({ username: "adventurer", level: 1, xp: 20, xp_max: 100 });
}
