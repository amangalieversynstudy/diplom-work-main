import "../styles/globals.css";
import { Toaster } from "sonner";

export default function MyApp({ Component, pageProps }) {
  return (
    <>
      <Component {...pageProps} />
      <Toaster richColors position="top-right" />
    </>
  );
}
