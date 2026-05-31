import Link from "next/link";
import Layout from "../components/Layout";
import { Ghost, Compass } from "lucide-react";
import { motion } from "framer-motion";
import { useI18n } from "../lib/i18n";

export default function Custom404() {
  const { t } = useI18n();
  return (
    <Layout hideFooter>
      <div className="flex flex-col items-center justify-center min-h-[80vh] text-center px-4 bg-[#0f0f11] font-display font-mono">
        <motion.div 
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8 }}
          className="relative"
        >
          <Ghost size={120} className="text-purple-500/50 mb-8 mx-auto animate-pulse" />
          <div className="absolute inset-0 bg-purple-500/20 blur-[100px] rounded-full z-[-1]" />
        </motion.div>
        
        <h1 className="text-6xl md:text-8xl font-bold text-text mb-4 tracking-tighter">
          404
        </h1>
        <h2 className="text-2xl md:text-3xl text-purple-400 mb-6 font-semibold">
          {t("notFound.subtitle")}
        </h2>
        <p className="text-[#888] max-w-md mx-auto mb-10 text-lg">
          {t("notFound.body")}
        </p>
        
        <Link 
          href="/worlds"
          className="inline-flex items-center gap-2 px-8 py-4 rounded-xl bg-purple-600/20 border border-[#222] text-purple-400 hover:bg-purple-600/40 hover:text-white transition-all duration-300 shadow-[0_0_20px_rgba(168,85,247,0.15)] hover:shadow-[0_0_30px_rgba(168,85,247,0.3)]"
        >
          <Compass size={20} />
          {t("notFound.back")}
        </Link>
      </div>
    </Layout>
  );
}