import Link from "next/link";
import Layout from "../components/Layout";
import { Ghost, Compass } from "lucide-react";
import { motion } from "framer-motion";
import { useI18n } from "../lib/i18n";

export default function Custom404() {
  const { t } = useI18n();
  return (
    <Layout hideFooter>
      <div className="flex flex-col items-center justify-center min-h-[80vh] text-center px-4 font-display">
        <motion.div 
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8 }}
          className="relative"
        >
          <Ghost size={120} aria-hidden="true" className="text-primary/50 mb-8 mx-auto animate-pulse" />
          <div className="absolute inset-0 bg-primary/20 blur-[100px] rounded-full z-[-1]" />
        </motion.div>
        
        <h1 className="text-6xl md:text-8xl font-bold text-text mb-4 tracking-tighter">
          404
        </h1>
        <h2 className="text-2xl md:text-3xl text-primary mb-6 font-semibold">
          {t("notFound.subtitle")}
        </h2>
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