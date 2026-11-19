import api from "./api";

export async function fetchLessons() {
  const { data } = await api.get("/lessons");
  return data;
}

export async function fetchLesson(lessonId, unit) {
  const { data } = await api.get(`/lessons/${lessonId}`, {
    params: unit ? { unit } : {},
  });
  return data;
}

export async function fetchQuiz(lessonId, count = 10, unit) {
  const { data } = await api.get(`/lessons/${lessonId}/quiz`, {
    params: { count, ...(unit ? { unit } : {}) },
  });
  return data;
}

export async function submitQuiz(lessonId, results, unit) {
  const { data } = await api.post(
    `/lessons/${lessonId}/quiz/submit`,
    { lesson_id: lessonId, results },
    { params: unit ? { unit } : {} }
  );
  return data;
}

export async function fetchProgress() {
  const { data } = await api.get("/progress");
  return data;
}

export async function submitStudyAnswer(vocabularyId, answer, correct) {
  const { data } = await api.post("/progress/study-answer", {
    vocabulary_id: vocabularyId,
    answer,
    correct,
  });
  return data;
}

export async function analyzeMistake(mistakeData) {
  const { data } = await api.post("/lessons/quiz/analyze-mistake", mistakeData);
  return data;
}

export async function analyzeAllMistakes(mistakes) {
  const { data } = await api.post("/lessons/quiz/analyze-all-mistakes", {
    mistakes,
  });
  return data;
}

export async function createAssessment(domain, level, skipLearning = false, placementTarget = null) {
  const { data } = await api.post("/assessments", {
    domain,
    level,
    skip_learning: skipLearning,
    placement_target: placementTarget,
  });
  return data;
}

export async function fetchAssessment(attemptId) {
  const { data } = await api.get(`/assessments/attempts/${attemptId}`);
  return data;
}

export async function submitAssessment(attemptId, answers) {
  const { data } = await api.post(`/assessments/attempts/${attemptId}/submit`, { answers });
  return data;
}
