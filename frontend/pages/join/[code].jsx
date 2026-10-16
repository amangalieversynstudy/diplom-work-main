import { useRouter } from "next/router";
import Layout from "../../components/Layout";
import JoinClassPanel from "../../components/JoinClassPanel";

// Ссылка-приглашение от преподавателя: /join/<код>.
export default function JoinByCode() {
  const router = useRouter();
  if (!router.isReady) return <Layout />;
  return (
    <Layout>
      <div className="max-w-md mx-auto mt-24 mb-10 px-4">
        <JoinClassPanel initialCode={String(router.query.code || "")} />
      </div>
    </Layout>
  );
}
