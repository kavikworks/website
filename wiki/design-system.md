# Kavik Works — Liquid Glass Design System

Style spec for matching the kavikworks.com redesign (July 2026). Written so an
agent with no access to this repo can restyle any internal page (e.g. the
portal) to match. Everything is vanilla CSS/JS — no frameworks, no build step,
no external assets beyond Google Fonts.

Reference implementations: `index.html` and `intake.html` on kavikworks.com
(view-source works; all CSS is inline in `<head>`).

---

## 1. Foundations

### Fonts

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Space+Grotesk:wght@500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
```

- **Space Grotesk** — headings only (`h1–h3`), weight 600–700, tight tracking
- **Inter** — body, labels, buttons
- **JetBrains Mono** — eyebrows/kickers, timestamps, tags, log lines, numbers in tables

If the portal can't reach Google Fonts (offline VPN box), system fallbacks are
fine: `-apple-system` for sans, `'SF Mono', monospace` for mono. The tokens
below already include fallbacks.

### Design tokens

```css
:root {
  --bg: #05060a;                        /* near-black, slightly blue */
  --ink: #eef1f6;                       /* headings, emphasized text */
  --ink-dim: #9aa3b2;                   /* body text */
  --ink-faint: #5c6472;                 /* hints, timestamps, footers */
  --cyan: #5eead4;                      /* primary accent */
  --violet: #a78bfa;                    /* secondary accent */
  --blue: #60a5fa;                      /* tertiary accent */
  --green: #34d399;                     /* success only */
  --edge: rgba(255,255,255,0.09);       /* default borders */
  --edge-bright: rgba(255,255,255,0.22);/* hover borders */
  --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  --font-display: 'Space Grotesk', 'Inter', sans-serif;
  --font-mono: 'JetBrains Mono', 'SF Mono', monospace;
}
```

Accent usage rules:
- Cyan is the workhorse accent (focus rings, live dots, list arrows, links-on-hover).
- Violet and blue appear mostly inside gradients and tag colors — never as large fills.
- For errors add `--red: #f87171` (portal will need it; the marketing site doesn't use one).
- Never use saturated accent colors as backgrounds — glass stays white-on-dark;
  accents are for text, borders, dots, and glows.

### Base styles

```css
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html { scroll-behavior: smooth; font-size: 16px; }
body {
  font-family: var(--font-sans);
  color: var(--ink-dim);
  background: var(--bg);
  line-height: 1.65;
  -webkit-font-smoothing: antialiased;
  overflow-x: hidden;
}
h1, h2, h3 { font-family: var(--font-display); color: var(--ink); line-height: 1.12; font-weight: 600; }
h1 { font-size: clamp(2.1rem, 4vw, 3.1rem); letter-spacing: -0.03em; }
h2 { font-size: clamp(1.4rem, 2.5vw, 1.9rem); letter-spacing: -0.02em; }
a { color: var(--ink); text-decoration: none; }
```

### Signature text treatments

```css
/* Eyebrow / kicker — appears above every heading */
.mono {
  font-family: var(--font-mono); font-size: 0.72rem;
  text-transform: uppercase; letter-spacing: 0.16em;
  color: var(--ink-faint);
}

/* Gradient accent text — used on ONE phrase per page, in the h1 */
.grad-text {
  background: linear-gradient(100deg, var(--cyan), var(--blue) 55%, var(--violet));
  -webkit-background-clip: text; background-clip: text; color: transparent;
}
```

---

## 2. Aurora backdrop (the "living" background)

Fixed behind everything. Three blurred color blobs drifting slowly + a faint
dot grid that fades toward the edges. Copy verbatim:

```html
<div class="aurora" aria-hidden="true">
  <div class="blob blob-1"></div>
  <div class="blob blob-2"></div>
  <div class="blob blob-3"></div>
</div>
```

```css
.aurora { position: fixed; inset: 0; z-index: -2; overflow: hidden; background: var(--bg); }
.aurora::after {
  content: ''; position: absolute; inset: 0;
  background-image: radial-gradient(rgba(255,255,255,0.028) 1px, transparent 1px);
  background-size: 28px 28px;
  mask-image: radial-gradient(ellipse 70% 60% at 50% 30%, black 20%, transparent 80%);
  -webkit-mask-image: radial-gradient(ellipse 70% 60% at 50% 30%, black 20%, transparent 80%);
}
.blob { position: absolute; border-radius: 50%; filter: blur(90px); opacity: 0.35; will-change: transform; }
.blob-1 { width: 620px; height: 620px; top: -220px; left: -120px;
  background: radial-gradient(circle, rgba(94,234,212,0.24), transparent 65%);
  animation: drift-1 26s ease-in-out infinite alternate; }
.blob-2 { width: 720px; height: 720px; top: -140px; right: -220px;
  background: radial-gradient(circle, rgba(167,139,250,0.22), transparent 65%);
  animation: drift-2 32s ease-in-out infinite alternate; }
.blob-3 { width: 540px; height: 540px; top: 55%; left: 30%;
  background: radial-gradient(circle, rgba(96,165,250,0.13), transparent 65%);
  animation: drift-3 38s ease-in-out infinite alternate; }
@keyframes drift-1 { to { transform: translate(140px, 90px) scale(1.15); } }
@keyframes drift-2 { to { transform: translate(-120px, 130px) scale(0.9); } }
@keyframes drift-3 { to { transform: translate(90px, -110px) scale(1.1); } }
```

For a dense dashboard, consider dropping blob opacity to `0.25` so charts and
tables stay readable.

---

## 3. Liquid glass card (the core primitive)

Every card, panel, and widget uses this one class. It combines: gradient glass
fill, backdrop blur, a specular top-edge highlight, deep soft shadow, and a
cursor-tracking sheen.

```css
.glass {
  position: relative;
  background: linear-gradient(160deg, rgba(255,255,255,0.07), rgba(255,255,255,0.02) 45%, rgba(255,255,255,0.045));
  border: 1px solid var(--edge);
  border-radius: 20px;
  backdrop-filter: blur(18px) saturate(1.5);
  -webkit-backdrop-filter: blur(18px) saturate(1.5);
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.12),   /* specular top edge */
    inset 0 -1px 0 rgba(255,255,255,0.03),
    0 18px 46px -18px rgba(0,0,0,0.6);
  overflow: hidden;
  transition: border-color 0.35s ease, transform 0.35s ease, box-shadow 0.35s ease;
}
/* cursor-following sheen (JS sets --mx/--my, see §7) */
.glass::before {
  content: ''; position: absolute; inset: 0; border-radius: inherit;
  background: radial-gradient(420px circle at var(--mx, 50%) var(--my, -20%),
    rgba(255,255,255,0.08), transparent 55%);
  opacity: 0; transition: opacity 0.4s ease; pointer-events: none;
}
.glass:hover::before { opacity: 1; }
.glass:hover { border-color: var(--edge-bright); }
.glass > * { position: relative; }  /* keep content above the ::before sheen */
```

Notes:
- On the marketing site, clickable/marketing cards also lift on hover
  (`transform: translateY(-3px)`). For a dashboard, **skip the lift** on
  data panels — it's distracting when scanning; keep it only on links/actions.
- Card padding: `1.9rem` for content cards, `2.4rem` for form cards.
- Radius scale: 20px cards, 16px small chips, 12px inputs, 100px pills/buttons.
- Featured/highlight variant (used on the primary pricing card):

```css
.glass.featured {
  border-color: rgba(94,234,212,0.28);
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.14),
    0 0 44px -14px rgba(94,234,212,0.28),
    0 18px 46px -18px rgba(0,0,0,0.6);
}
```

---

## 4. Navigation — floating glass pill

Detached from the top edge, pill-shaped, blurred:

```css
nav { position: fixed; top: 14px; left: 0; right: 0; z-index: 100; pointer-events: none; }
.nav-pill {
  pointer-events: auto;
  max-width: 1120px; margin: 0 auto;
  display: flex; align-items: center; justify-content: space-between;
  padding: 0.55rem 0.65rem 0.55rem 1.25rem;
  background: rgba(10,12,18,0.55);
  border: 1px solid var(--edge);
  border-radius: 100px;
  backdrop-filter: blur(22px) saturate(1.6);
  -webkit-backdrop-filter: blur(22px) saturate(1.6);
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.1), 0 12px 32px -12px rgba(0,0,0,0.6);
}
@media (max-width: 1180px) { .nav-pill { margin: 0 1rem; } }
```

Logo mark: 26px rounded square outlined in `--ink-faint` with an 8px inner
square filled `linear-gradient(135deg, var(--cyan), var(--violet))`. Wordmark
in Space Grotesk 700. For the portal, suffix the wordmark with a mono label:
`Kavik Works <span class="mono">· portal</span>`.

Give the page enough top padding to clear the pill: first section starts at
`padding-top: 9.5rem` (or ~6rem for a dense dashboard).

---

## 5. Buttons & interactive bits

```css
/* Primary — light gradient pill with cyan glow (dark text!) */
.btn-primary {
  display: inline-flex; align-items: center; gap: 0.5rem;
  padding: 0.8rem 1.7rem; border-radius: 100px;
  color: #05060a; font-weight: 600; font-size: 0.95rem;
  background: linear-gradient(120deg, #d7fff5, #ffffff 50%, #e6dcff);
  box-shadow: 0 0 24px -6px rgba(94,234,212,0.4);
  border: none; cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}
.btn-primary:hover { transform: translateY(-2px); box-shadow: 0 0 34px -6px rgba(167,139,250,0.55); }

/* Secondary — glass pill */
.btn-secondary {
  display: inline-flex; align-items: center; gap: 0.5rem;
  padding: 0.8rem 1.7rem; border-radius: 100px;
  background: rgba(255,255,255,0.04); color: var(--ink-dim);
  border: 1px solid var(--edge);
  backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
  font-weight: 500; font-size: 0.95rem; transition: all 0.2s; cursor: pointer;
}
.btn-secondary:hover { border-color: var(--edge-bright); color: var(--ink); }
```

```css
/* Pulsing live dot — pair with mono text: "live", "daemon running", etc. */
.live-dot {
  width: 7px; height: 7px; border-radius: 50%;
  background: var(--cyan);
  animation: ping 2.4s ease-out infinite;
}
@keyframes ping {
  0%   { box-shadow: 0 0 0 0 rgba(94,234,212,0.45); }
  70%  { box-shadow: 0 0 0 9px rgba(94,234,212,0); }
  100% { box-shadow: 0 0 0 0 rgba(94,234,212,0); }
}
```

### Form fields (from intake.html)

```css
.field input, .field select, .field textarea {
  width: 100%; padding: 0.75rem 1rem;
  background: rgba(255,255,255,0.035);
  border: 1px solid var(--edge); border-radius: 12px;
  color: var(--ink); font-family: var(--font-sans); font-size: 0.925rem;
  transition: border-color 0.2s, background 0.2s, box-shadow 0.2s; outline: none;
}
.field input:focus, .field select:focus, .field textarea:focus {
  border-color: rgba(94,234,212,0.45);
  background: rgba(255,255,255,0.055);
  box-shadow: 0 0 0 3px rgba(94,234,212,0.12);   /* cyan focus ring */
}
```

---

## 6. Portal-specific components

The marketing site doesn't have these; here's how to extend the language to
dashboard furniture so it still reads as one system.

### Metric / stat tile

```css
.stat { padding: 1.6rem 1.8rem; border-radius: 18px; }  /* + .glass */
.stat-num { font-family: var(--font-display); font-size: 2rem; font-weight: 700;
  color: var(--ink); letter-spacing: -0.02em; }          /* or .grad-text */
.stat-label { font-size: 0.85rem; color: var(--ink-faint); margin-top: 0.15rem; }
```

### Status badges / tags

Outlined, tinted, mono, lowercase — never solid fills:

```css
.tag {
  font-family: var(--font-mono); font-size: 0.62rem;
  padding: 0.1rem 0.5rem; border-radius: 4px;
  border: 1px solid var(--edge); background: rgba(255,255,255,0.04);
}
.tag.ok    { color: var(--green);  border-color: rgba(52,211,153,0.3); }
.tag.info  { color: var(--blue);   border-color: rgba(96,165,250,0.3); }
.tag.warn  { color: #fbbf24;       border-color: rgba(251,191,36,0.3); }
.tag.error { color: #f87171;       border-color: rgba(248,113,113,0.3); }
.tag.ai    { color: var(--cyan);   border-color: rgba(94,234,212,0.3); }
```

### Data tables

Put the table inside a `.glass` panel with zero padding; keep the table itself
transparent:

```css
.glass.table-panel { padding: 0; }
table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
thead th {
  font-family: var(--font-mono); font-size: 0.68rem; font-weight: 500;
  text-transform: uppercase; letter-spacing: 0.14em; color: var(--ink-faint);
  text-align: left; padding: 0.9rem 1.25rem;
  border-bottom: 1px solid var(--edge);
  background: rgba(255,255,255,0.025);
}
tbody td { padding: 0.8rem 1.25rem; border-bottom: 1px solid rgba(255,255,255,0.05); color: var(--ink-dim); }
tbody tr:last-child td { border-bottom: none; }
tbody tr:hover { background: rgba(255,255,255,0.025); }
```

Numbers/IDs/timestamps in table cells: `font-family: var(--font-mono)`.

### Log / console panel

See the hero console on kavikworks.com index. Recipe: `.glass` with zero
padding → header bar (`padding: 0.85rem 1.25rem; border-bottom: 1px solid
var(--edge); background: rgba(255,255,255,0.025)`) containing three 10px
traffic-light dots (`background: rgba(255,255,255,0.12)`) + a `.mono` title →
mono body (`font-size: 0.78rem`) with rows of `timestamp · message · .tag`.
New rows animate in with:

```css
.evt { opacity: 0; transform: translateY(8px); animation: evt-in 0.5s ease forwards; }
@keyframes evt-in { to { opacity: 1; transform: none; } }
```

For the portal, feed it real daemon events instead of the marketing site's
simulated loop.

---

## 7. JavaScript behaviors

**Cursor sheen** (required for the `.glass::before` effect to move):

```js
if (window.matchMedia('(pointer: fine)').matches) {
  document.querySelectorAll('.glass').forEach(card => {
    card.addEventListener('pointermove', e => {
      const r = card.getBoundingClientRect();
      card.style.setProperty('--mx', ((e.clientX - r.left) / r.width * 100) + '%');
      card.style.setProperty('--my', ((e.clientY - r.top) / r.height * 100) + '%');
    });
  });
}
```

**Scroll reveal** (optional on a dashboard — skip if content should be
instantly visible):

```js
const observer = new IntersectionObserver((entries) => {
  entries.forEach(e => { if (e.isIntersecting) e.target.classList.add('visible'); });
}, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });
document.querySelectorAll('.fade-in').forEach(el => observer.observe(el));
```
```css
.fade-in { opacity: 0; transform: translateY(22px); transition: opacity 0.7s ease, transform 0.7s ease; }
.fade-in.visible { opacity: 1; transform: translateY(0); }
```

---

## 8. Accessibility & motion (non-negotiable)

```css
@media (prefers-reduced-motion: reduce) {
  .blob, .live-dot { animation: none !important; }
  .fade-in { opacity: 1; transform: none; transition: none; }
  .evt { animation: none; opacity: 1; transform: none; }
  html { scroll-behavior: auto; }
}
```

- Aurora wrapper gets `aria-hidden="true"`.
- Every form label gets `for`/`id`.
- Body text stays `--ink-dim` on `--bg` (≈7:1). Don't set long text in
  `--ink-faint` — hints and timestamps only.

---

## 9. Layout rhythm

- Content max-width: `1120px` marketing / full-bleed grids fine for the portal;
  forms and reading content cap at `860px`.
- Page padding: `0 2rem` desktop, collapses naturally on mobile.
- Card gaps: `1.25–1.5rem`. Section padding: `6rem 0` marketing, `2–3rem` dashboard.
- Grids collapse to 1 column at `max-width: 768px`; 4-col grids step through
  2-col at `900px`.

## 10. Voice/tone for UI copy

Lowercase mono for system text ("live pipeline", "response SLA met"),
sentence-case for everything else, no exclamation marks in UI chrome, numbers
formatted with mono font. The brand sound: plain, measured, slightly dry.
