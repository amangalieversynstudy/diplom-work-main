import Layout from "../components/Layout";
import Card from "../components/Card";
import XPBar from "../components/XPBar";
import Button from "../components/Button";

export default function Home() {
  return (
    <Layout>
      <div className="grid md:grid-cols-3 gap-6">
        <Card title="Adventurer" subtitle="Level 1">
          <XPBar current={20} max={100} />
        </Card>
        <Card title="Next mission" subtitle="Start your first quest">
          <Button onClick={() => (window.location.href = "/worlds")}>
            Go to Worlds
          </Button>
        </Card>
        <Card title="Tips" subtitle="How to earn XP faster">
          <ul className="list-disc ml-5 text-sm text-white/80">
            <li>Complete Intro mission</li>
            <li>Unlock Gate after Intro</li>
          </ul>
        </Card>
      </div>
    </Layout>
  );
}
