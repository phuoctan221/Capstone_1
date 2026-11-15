import { clampPercent } from "./domains.js";

export const CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"];

export function nextCefrLevel(level) {
  const index = CEFR_LEVELS.indexOf(String(level || "").toUpperCase());
  return index >= 0 && index < CEFR_LEVELS.length - 1 ? CEFR_LEVELS[index + 1] : null;
}

function levelRank(lesson) {
  const index = CEFR_LEVELS.indexOf(String(lesson?.level || "").toUpperCase());
  return index < 0 ? CEFR_LEVELS.length : index;
}

export function computeLevelProgress(lessons, domains) {
  const list = Array.isArray(lessons) ? lessons : [];
  const chosen = Array.isArray(domains) ? domains : [];
  if (!list.length || !chosen.length) return null;

  const items = [];
  let remaining = 0;
  let learned = 0;
  let total = 0;

  for (const domain of chosen) {
    const domainLessons = list
      .filter((lesson) => lesson && lesson.topic === domain.id && Number(lesson.word_count) > 0)
      .sort((a, b) => levelRank(a) - levelRank(b));
    if (!domainLessons.length) continue;

    const target = domainLessons.find((lesson) => !lesson.completed);

    if (!target) {
      items.push({
        domain: domain.id,
        label: domain.label,
        glyph: domain.glyph,
        tone: domain.tone,
        level: null,
        nextLevel: null,
        remaining: 0,
        total: 0,
        learned: 0,
        completed: true,
        href: null,
      });
      continue;
    }

    const targetTotal = Number(target.word_count) || 0;
    const targetLearned = Math.min(Number(target.learned_count) || 0, targetTotal);
    const targetRemaining = Math.max(targetTotal - targetLearned, 0);
    remaining += targetRemaining;
    learned += targetLearned;
    total += targetTotal;

    items.push({
      domain: domain.id,
      label: domain.label,
      glyph: domain.glyph,
      tone: domain.tone,
      level: target.level,
      nextLevel: nextCefrLevel(target.level),
      remaining: targetRemaining,
      total: targetTotal,
      learned: targetLearned,
      completed: false,
      href: `/lessons/${target.slug || target.id}?unit=${target.next_unit || 1}`,
    });
  }

  if (!items.length) return null;

  const active = items.filter((item) => !item.completed);
  const targetLevels = [...new Set(active.map((item) => item.level).filter(Boolean))];
  const nextLevels = [...new Set(active.map((item) => item.nextLevel).filter(Boolean))];
  const cta = active
    .filter((item) => item.href)
    .sort((a, b) => a.remaining - b.remaining)[0] || null;

  return {
    remaining,
    learned,
    total,
    percent: total ? clampPercent((learned / total) * 100) : 100,
    items,
    targetLevel: targetLevels.length === 1 ? targetLevels[0] : null,
    nextLevel: nextLevels.length === 1 ? nextLevels[0] : null,
    allCompleted: active.length === 0,
    href: cta?.href || "/learn",
  };
}
