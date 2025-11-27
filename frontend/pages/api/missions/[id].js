const missions = [
  { id: 1, name: "Intro", status: "completed", prereq: null, reward: 25 },
  { id: 2, name: "Gate", status: "available", prereq: "Intro", reward: 50 },
  { id: 3, name: "Repeatable", status: "locked", prereq: "Gate", reward: 10 },
];

export default function handler(req, res) {
  const { id } = req.query;
  const mission = missions.find((m) => String(m.id) === String(id));
  if (!mission) return res.status(404).json({ detail: "Not found" });
  if (req.method === "GET") return res.status(200).json(mission);
  return res.status(405).json({ detail: "Method not allowed" });
}
