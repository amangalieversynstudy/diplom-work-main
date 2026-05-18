# Frontend Redesign — Apply Instructions

## What changed

### New colour palette (Jade Forest × Terracotta)
Old: purple `#7C3AED` / cyan `#22D3EE` / gold `#F59E0B`
New: jade `#2ECC8A` / terracotta `#E8693A` / warm-gold `#D4A853`

Background shifted from cold navy to deep forest green `#06100D`.

### New fonts
Old: Cinzel Decorative + Space Grotesk
New: **Playfair Display** (display/headings) + **DM Sans** (body) + **JetBrains Mono** (code)

### Added libraries
- `gsap` + `@gsap/react` — scroll-triggered animations
- `lenis` — smooth inertial scrolling (replaces default browser scroll)

### Files changed
| File | What changed |
|---|---|
| `package.json` | Added `gsap`, `@gsap/react`, `lenis` |
| `tailwind.config.js` | New colour tokens, font families, shadows |
| `styles/globals.css` | Complete rewrite — forest palette, Lenis CSS, GSAP helpers |
| `pages/_app.js` | Lenis + GSAP ScrollTrigger initialised once for all pages |
| `pages/index.js` | Full redesign: Hero, Stats, Programs, How It Works, CTA |
| `pages/worlds/index.jsx` | GSAP card animations, new island cards |
| `components/Layout.jsx` | New nav — logomark, scroll-aware header, green CTA button |
| `components/Card.jsx` | Jade/ember/gold tone variants, highlight line, hover lift |
| `components/Button.jsx` | Jade primary, terracotta accent, cleaner variants |
| `components/XPBar.jsx` | Jade gradient bar with glow |

---

## How to apply

```bash
# 1. Copy changed files into your repo
cp -r outputs/frontend/* your-repo/frontend/

# 2. Install new dependencies
cd your-repo/frontend
npm install

# 3. Run dev server
npm run dev
```

## Lenis + GSAP architecture

Lenis is initialised once in `_app.js`. It syncs with GSAP ScrollTrigger so
scroll-triggered animations play at the right scroll position:

```js
// Already done in _app.js — no extra setup needed
lenis.on("scroll", ScrollTrigger.update)
gsap.ticker.add((time) => lenis.raf(time * 1000))
```

### Adding GSAP animations to new pages

```js
useEffect(() => {
  if (typeof window === "undefined") return
  import("gsap").then(({ gsap }) => {
    import("gsap/ScrollTrigger").then(({ ScrollTrigger }) => {
      gsap.registerPlugin(ScrollTrigger)

      gsap.from(".my-element", {
        scrollTrigger: { trigger: ".my-section", start: "top 80%" },
        y: 40, opacity: 0, duration: 0.7, stagger: 0.15
      })
    })
  })
}, [])
```

### Programmatic Lenis control

```js
// Scroll to a section
window.__lenis?.scrollTo("#section-id", { duration: 1.5 })

// Pause scrolling (e.g. modal open)
window.__lenis?.stop()
window.__lenis?.start()
```

---

## Colour reference

```css
--primary:   #2ECC8A   /* jade green */
--jade:      #1AA870   /* deep jade */
--accent:    #E8693A   /* terracotta */
--ember:     #C0522A   /* deep terracotta */
--gold:      #D4A853   /* warm gold */
--bg:        #06100D   /* forest black */
--surface:   #0D1F18   /* dark forest */
--panel:     #122318   /* card bg */
--mist:      #E8F0EA   /* off-white text */
```

## Tailwind classes quick-ref

```
text-primary      → jade green
text-accent       → terracotta
text-gold         → warm gold
text-mist         → off-white
bg-surface        → card background
border-primary/12 → subtle jade border
```
