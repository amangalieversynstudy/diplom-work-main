import Link from "next/link";
import { useRouter } from "next/router";
import gsap from "gsap";

export default function TransitionLink({ href, children, className, onClick }) {
  const router = useRouter();

  const handleClick = (e) => {
    e.preventDefault();
    if (onClick) onClick();

    gsap.to(".page-transition-overlay", {
      yPercent: 0,
      duration: 0.7,
      ease: "power3.inOut",
      onComplete: () => {
        router.push(href);
      },
    });
  };

  return (
    <Link href={href} onClick={handleClick} className={className}>
      {children}
    </Link>
  );
}