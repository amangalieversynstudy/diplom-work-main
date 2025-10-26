import Layout from "../components/Layout";
import Card from "../components/Card";

const rows = [
  { user: "Alice", level: 3, xp: 250 },
  { user: "Bob", level: 2, xp: 120 },
];

export default function Leaderboard() {
  return (
    <Layout>
      <h1 className="text-2xl font-semibold mb-4">Leaderboard</h1>
      <Card>
        <table className="w-full text-sm">
          <thead className="text-white/70">
            <tr>
              <th className="text-left py-2">Player</th>
              <th className="text-left">Level</th>
              <th className="text-left">XP</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="border-t border-white/10">
                <td className="py-2">{r.user}</td>
                <td>{r.level}</td>
                <td>{r.xp}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </Layout>
  );
}
