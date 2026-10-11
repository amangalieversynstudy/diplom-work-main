import Link from "next/link";
import { useRouter } from "next/router";
import gsap from "gsap";
import { prefersReducedMotion } from "../lib/motion";

export default function TransitionLink({ href, children, className, onClick }) {
  const router = useRouter();

  const handleClick = (e) => {
    e.preventDefault();
    if (onClick) onClick();

    // If already on this page, don't play the overlay animation (it won't come back up)
    if (router.pathname === href || router.asPath === href) {
      return;
    }

    // без движения шторка не нужна: сразу переходим
    if (prefersReducedMotion()) {
      router.push(href);
      return;
    }

    try {
      window.sessionStorage.setItem("curtain", "1"); // новая страница поднимет шторку
    } catch {
      /* без хранилища шторка не поднимется сама, но и не опустится */
    }
    gsap.to(".page-transition-overlay", {
      yPercent: 0,
      duration: 0.2,
      ease: "power3.inOut",
    });
    router.push(href); // не ждём шторку: страница грузится параллельно
  };

  return (
    <Link href={href} onClick={handleClick} className={className}>
      {children}
    </Link>
  );
}