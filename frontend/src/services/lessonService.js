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
