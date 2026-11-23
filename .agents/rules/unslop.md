---
trigger: always_on
description: Unslop UI/UX design rules to eliminate generic AI-generated aesthetics and enforce intentional craft across frontend code.
globs: "**/frontend/**, **/*.jsx, **/*.tsx, **/*.vue, **/*.html, **/*.css, **/*.scss"
---

# Unslop UI & Frontend Craft Rules

When writing or editing frontend code (React, HTML, CSS, Tailwind, or styling systems), strictly follow the **Unslop** design philosophy. All UI must feel intentional, calm, and tailored to the product, rather than looking like generic vibecoded AI templates.

---

## 1. What to Eliminate Immediately (Slop Tells)

- ❌ **No Violet/Purple Hue Gradients**: Remove purple-to-blue or magenta gradients across backgrounds, headers, surfaces, and buttons (`linear-gradient(135deg, #4f46e5, #7c3aed)`).
- ❌ **No Gradient Text**: Never use `bg-clip-text` or `-webkit-background-clip: text` with multi-hue gradients.
- ❌ **No Colored Glows or Neon Shadows**: Remove `box-shadow` with tinted neon color spread (e.g., `rgba(79, 70, 229, 0.35)`). Shadows must be neutral, soft, and small.
- ❌ **No Glowing Radial Blobs**: Remove background blur circles, floating gradient spheres, or orbs behind content.
- ❌ **No Emojis as UI Icons**: Never use emojis in navigation, labels, headers, or buttons (e.g. `Welcome back! 👋`, `✨`, `🚀`).
- ❌ **No Pill Mania**: Do not make every card, input, and avatar a pill (`border-radius: 9999px`).
- ❌ **No Uppercase Tracked Labels**: Do not use `text-xs uppercase tracking-widest` for section headers or menu items. Use natural sentence case.
- ❌ **No Hype Copy & Exclamation Marks**: Remove exclamation marks (`!`, `!!`). No empty buzzwords (`AI-powered`, `supercharge`, `seamless`, `magic`, `game-changing`).
- ❌ **No Looping or Jittery Motion**: Remove `animate-pulse`, `animate-ping`, infinite shimmers, floating keyframes, or `transition-all`.

---

## 2. Core Execution Passes

### 1. Spacing & Rhythm
- **4px Scale**: All margins, paddings, gaps, and heights must be multiples of 4 (4, 8, 12, 16, 20, 24, 32, 48px). No arbitrary one-off pixels (`mt-[13px]`, `p-[11px]`).
- **Grouping**: Space inside a group is smaller than space between groups.
- **Alignment**: Peer cards share identical padding; peer rows share identical height. Icons, labels, and numbers must align vertically on crisp column axes.

### 2. Restrained Color & Surfaces
- **One Neutral Ramp**: Background, elevated surfaces, borders, and text all share one neutral ramp tinted toward the product domain (e.g., slate, graphite, warm grey).
- **Quiet Chrome**: Navigation, buttons, cards, and sidebars remain neutral. Color belongs strictly to the user content (flashcards, mastery progress, charts), not the scaffolding.
- **Three Text Roles**: Primary (high contrast), secondary (subtitles/labels), and muted (meta/timestamps).
- **One Accent**: Used sparingly for the primary action or active selection. Accent text must meet at least 4.5:1 contrast against its background.
- **Hairline Borders**: Borders should be quiet hairlines using the text neutral at 6%–10% opacity (`rgba(15, 23, 42, 0.08)`).

### 3. Cohesive Icons
- Use a single line icon set (e.g., Lucide) across the entire application.
- Standardize on one size and stroke width (e.g., 16px or 18px with 1.5 stroke).
- Icons inherit the color of their text role (`currentColor` / muted); never assign multi-colored fills to generic icons.

### 4. Direct, Contextual Copy
- State what the page or component is in plain words (e.g., `Vocabulary List`, `October 2026`, `Search words`).
- Labels, buttons, and titles never end with trailing periods.
- Mock/sample data must look realistic with plausible domain names and numbers.

### 5. Intentional Typography
- Restrict font weights to **400 (regular)** and **500 (medium)**. Reserve **600 (semibold)** only for rare emphasis. Avoid 700–900 heavy weights for headings.
- Build visual hierarchy through size and color role, not brute font weight.
- Use `font-variant-numeric: tabular-nums` (or `tabular-nums` class) for all counts, timestamps, and statistics.
- Always use **Sentence case** for titles, headings, and buttons.

### 6. Desktop-First Proportions & Layout
- Maintain authentic web application proportions (sidebar ~240–280px, fluid main view capped at 1200–1440px). Avoid squeezing an app into a narrow centered mobile column on desktop.
- Keep one clear primary action button per view. Secondary actions should be quiet outlines or text links.

### 7. Precise Component Details
- **Nested Border Radius Rule**:
  $$R_{inner} = R_{outer} - \text{padding} \ge 4\text{px}$$
- Standard radii: Controls `8px–10px`, Cards `12px–16px`, Outer panels `14px–20px`.
- Status indicators: Use subtle 6px–8px solid status dots rather than flashing pills or glowing badges.

### 8. Motion & Transitions
- Transition only explicit properties: `color`, `background-color`, `border-color`, `opacity`, `transform`.
- Durations must be short and crisp (120ms to 200ms) with standard ease-out (`cubic-bezier(0, 0, 0.2, 1)`).
- Never animate layout geometry (`width`, `height`, `margin`, `padding`, `top`, `left`).

---

## 3. Pre-Commit Checklist

Before completing any UI change, verify:
- [ ] No purple gradients, glowing borders, or radial background washes remain.
- [ ] No emojis in UI buttons, titles, or navigational items.
- [ ] All padding and margin values conform to the 4px grid.
- [ ] Nested corner radii mathematically add up.
- [ ] Typography uses sentence case and weights stay between 400 and 600.
- [ ] Status and interactive states are subtle surface steps, not neon effects.
