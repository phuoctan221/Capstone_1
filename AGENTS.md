# Project Rules & Guidelines

Welcome to the **SmartVocab** repository. All AI assistants, agents, and contributors operating in this codebase must adhere to the following core guidelines.

---

## 🎨 UI & Frontend Standards: Unslop Rules

When writing, refactoring, or generating code in `frontend/` (React, JSX, HTML, CSS), **strictly apply the Unslop design principles** (detailed in `.agents/rules/unslop.md` and `.agents/skills/unslop/SKILL.md`):

1. **Eliminate AI "Slop" Tells**:
   - ❌ **No purple/violet-to-blue gradients** on surfaces, headers, or buttons (`linear-gradient(135deg, #4f46e5, #7c3aed)`).
   - ❌ **No colored glow shadows or neon borders** (`box-shadow: 0 4px 12px rgba(79, 70, 229, 0.35)`). Use quiet, neutral, soft shadows only.
   - ❌ **No background blur blobs, gradient orbs, or floating decorative geometry**.
   - ❌ **No emojis as UI icons or labels** (`👋`, `✨`, `🚀`). Use standard SVG line icons (e.g. Lucide) at uniform stroke (1.5) and size (16–18px).
   - ❌ **No "pill mania"** (`border-radius: 9999px` on every element). Use deliberate nested radii: controls 8–10px, cards 12–16px, panels 14–20px.
   - ❌ **No uppercase tracked labels** (`text-xs uppercase tracking-widest`). Use sentence case.
   - ❌ **No hype copy or exclamation marks** (`AI-powered`, `supercharge`, `seamless`, `!`). Keep copy direct, clear, and contextual.
   - ❌ **No looping animations or heavy `transition-all`** (`animate-pulse`, `animate-ping`).

2. **Intentional Craft & Spacing**:
   - **4px Scale**: All paddings, margins, gaps, and heights must be multiples of 4 (4, 8, 12, 16, 20, 24, 32px).
   - **Quiet Chrome**: Scaffolding, headers, sidebars, and cards use one neutral tinted ramp. Color is reserved for content (learning progress, flashcard status).
   - **Typography**: Weights 400 and 500 (600 rare). Hierarchy through size and contrast, not brute bold weights. Tabular numerals for statistics.
   - **Nested Radius Rule**: $R_{inner} = R_{outer} - \text{padding} \ge 4\text{px}$.

---

## 💻 Tech Stack Guidelines

- **Frontend**: React 18, Vite, React Router 6, CSS modules / vanilla CSS styling.
- **Backend**: FastAPI / Python backend with PostgreSQL / SQLAlchemy / Alembic (located in `backend/`).
- Follow clean architecture, single-responsibility components, and ensure accessibility standards (WCAG contrast $\ge 4.5:1$).
