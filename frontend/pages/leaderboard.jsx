import Layout from "../components/Layout";
import Card from "../components/Card";
import Badge from "../components/Badge";

const rows = [
  { user: "Alice the Arcanist", level: 4, xp: 420, streak: 5 },
  { user: "Bob the Ranger", level: 3, xp: 260, streak: 3 },
  { user: "Cecilia", level: 2, xp: 180, streak: 2 },
  { user: "Dante", level: 1, xp: 90, streak: 1 },
];

export default function Leaderboard() {
  return (
    <Layout>
      <section className="mb-6">
        <p className="text-xs uppercase tracking-[0.35em] text-white/60">
          Hall of legends
        </p>
        <h1 className="text-3xl font-display">Leaderboard</h1>
        <p className="text-sm text-white/70">Completion streak boosts ranking every midnight reset.</p>
      </section>
      <Card tone="night">
        <table className="w-full text-sm">
          <thead className="text-white/70 text-xs uppercase tracking-[0.3em]">
            <tr>
              <th className="text-left py-3">Rank</th>
              <th className="text-left">Player</th>
              <th className="text-left">Level</th>
              <th className="text-left">XP</th>
              <th className="text-left">Streak</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={r.user} className="border-t border-white/10">
                <td className="py-3 text-white/60">#{i + 1}</td>
                <td className="py-3 font-semibold">{r.user}</td>
                <td>{r.level}</td>
                <td>{r.xp}</td>
                <td>
                  <Badge status={r.streak > 2 ? "available" : "locked"}>
                    {r.streak}d
                  </Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </Layout>
  );
}
