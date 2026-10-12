// Пиксельные портреты классов: сетка 16x16, один символ = один пиксель.
// Палитра: o/d тёмные чернила, k кожа, w светлый пергамент, r сургуч, c бирюза (primary),
// g золото, G золотая рамка, l кожа-ремень, s сталь, "." пусто.
export const PIXEL_SIZE = 16;

export const PIXEL_FILL = {
  o: "var(--ink-deep)",
  d: "var(--ink-deep)",
  e: "var(--ink-deep)",
  k: "var(--px-skin)",
  w: "var(--parchment-light)",
  r: "var(--wax)",
  c: "var(--primary)",
  g: "var(--gold)",
  G: "var(--gold-frame)",
  l: "var(--px-leather)",
  s: "var(--px-steel)",
};

export const PIXEL_ART = {
  // маг: остроконечная шляпа со звездой, борода, посох с шаром
  python: [
    ".......oo.......",
    "......orro...gg.",
    ".....orggro..gg.",
    "....orrggrro..l.",
    "..oGGGGGGGGGGol.",
    "....okkkkkko..l.",
    "....okekkeko..l.",
    "....owwwwwwo..l.",
    "...orrwwwwrro.l.",
    "..orrrrwwrrrrol.",
    "..orrrrrrrrrrol.",
    "..oGGGGGGGGGGol.",
    "..orrrrrrrrrrol.",
    "..orrrrrrrrrrol.",
    "..orrrrrrrrrrol.",
    "..orrrrrrrrrrol.",
  ],
  // арканист: глубокий капюшон, светящиеся глаза, раскрытая книга рун
  django: [
    "......oooo......",
    ".....occcco.....",
    "....occcccco....",
    "...occddddcco...",
    "...ocdgddgdco...",
    "...ocddddddco...",
    "...occcddccco...",
    "..occcccccccco..",
    ".occcccccccccco.",
    ".ocwwwwllwwwwco.",
    ".ocwggwllwggwco.",
    ".ocwwwwllwwwwco.",
    ".occcccccccccco.",
    ".occcccccccccco.",
    ".occcccccccccco.",
    ".occcccccccccco.",
  ],
  // рейнджер: кожаная кепка с пером, стальные наплечники, лук за плечом
  devops: [
    "................",
    "......oooo......",
    ".....ollllo.....",
    "....ollllllorr..",
    "..ollllllllllol.",
    "....okkkkkko..sl",
    "....okekkeko..sl",
    "....orrrrrro..sl",
    "..ossllllllssosl",
    "..osllssssllsosl",
    "..ollllssllllosl",
    "..oGGGGGGGGGGosl",
    "..ollllllllllol.",
    "..ollllllllllo..",
    "..ollllllllllo..",
    "..ollllllllllo..",
  ],
};
