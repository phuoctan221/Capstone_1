import api from "./api";

/** Compatibility with the previously shared backend ZIP.
 * The user's newer 48-test backend was not supplied, so the API contract
 * needs a verification pass before enabling session-specific endpoints.
 */
export async function submitPracticeAnswer({ vocabularyId, answer, skill, attemptId, responseTimeMs, hintUsed }) {
  const { data } = await api.post("/progress/study-answer", {
    vocabulary_id: vocabularyId,
    answer,
    skill,
    attempt_id: attemptId,
    response_time_ms: Math.min(600000, Math.max(0, Math.round(responseTimeMs))),
    hint_used: Boolean(hintUsed),
  });
  return data;
}
