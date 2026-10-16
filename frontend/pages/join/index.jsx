import Layout from "../../components/Layout";
import JoinClassPanel from "../../components/JoinClassPanel";

// Ввести код класса руками.
export default function JoinIndex() {
  return (
    <Layout>
      <div className="max-w-md mx-auto mt-24 mb-10 px-4">
        <JoinClassPanel />
      </div>
    </Layout>
  );
}
