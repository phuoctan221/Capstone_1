import { SKILLS } from "../constants/domains";

/** Normalize optional backend /progress/mastery responses without inventing scores.
 * Supports averages, skills/mastery objects, or an array of per-word mastery.
 */
export function summarizeMastery(data) {
  if (!data) return null;
  const group = data?.averages || data?.skills || data?.mastery || data?.average_mastery || null;
  const direct = group && Object.fromEntries(SKILLS.map(({ id }) => [id, Number(group[id])]).filter(([, value]) => Number.isFinite(value)));
  if (direct && Object.keys(direct).length === SKILLS.length) return direct;
  const rows = Array.isArray(data) ? data : (data.items || data.words || data.states || []);
  if (!Array.isArray(rows) || !rows.length) return null;
  const sums = { meaning: 0, spelling: 0, context: 0 };
  let valid = 0;
  for (const row of rows) {
    const source = row.mastery || row;
    if (SKILLS.every((skill) => Number.isFinite(Number(source[skill.id])))) {
      valid++;
      for (const skill of SKILLS) sums[skill.id] += Number(source[skill.id]);
    }
  }
  if (!valid) return null;
  return Object.fromEntries(SKILLS.map(({ id }) => [id, Math.round(sums[id] / valid)]));
}

export function normalizeHistory(data) {
  const rows = Array.isArray(data) ? data : (data?.items || data?.history || data?.attempts || []);
  return Array.isArray(rows) ? rows : [];
}
