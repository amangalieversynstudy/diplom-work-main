import Link from "next/link";
import Layout from "../components/Layout";
import EmptyScroll from "../components/EmptyScroll";
import { Ghost, Compass } from "lucide-react";
import { useI18n } from "../lib/i18n";

export default function Custom404() {
  const { t } = useI18n();
  return (
    <Layout hideFooter>
      <div className="flex flex-col items-center justify-center min-h-[80vh] text-center px-4 font-display">
        <h1 className="text-6xl md:text-8xl font-bold text-text mb-8 tracking-tighter">
          404
        </h1>
        <EmptyScroll icon={Ghost} className="w-full max-w-md mb-6">
          {t("notFound.subtitle")}
        </EmptyScroll>
        <p className="text-muted max-w-md mx-auto mb-10 text-lg">
          {t("notFound.body")}
        </p>
        
        <Link 
          href="/worlds"
          className="inline-flex min-h-[44px] items-center gap-2 px-8 py-4 rounded-xl bg-primary/10 border border-primary/30 text-primary hover:bg-primary hover:text-on-primary transition-all duration-300"
        >
          <Compass size={20} aria-hidden="true" />
          {t("notFound.back")}
        </Link>
      </div>
    </Layout>
  );
}