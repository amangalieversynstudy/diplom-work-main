import Link from "next/link";

// Обычный мгновенный переход Next.js. Раньше здесь опускалась зелёная шторка на весь экран при каждом клике:
// она выглядела как медленная загрузка, поэтому её больше нет. Имя компонента оставлено для старых импортов.
export default function TransitionLink({ href, children, className, onClick, ...rest }) {
  return (
    <Link href={href} onClick={onClick} className={className} {...rest}>
      {children}
    </Link>
  );
}
