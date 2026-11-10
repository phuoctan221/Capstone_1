import api from "./api";

export async function fetchLessons() {
  const { data } = await api.get("/lessons");
  return data;
}

export async function fetchLesson(lessonId) {
  const { data } = await api.get(`/lessons/${lessonId}`);
  return data;
}

export async function fetchQuiz(lessonId, count = 10) {
  const { data } = await api.get(`/lessons/${lessonId}/quiz`, {
    params: { count },
  });
  return data;
}

export async function submitQuiz(lessonId, results) {
  const { data } = await api.post(`/lessons/${lessonId}/quiz/submit`, {
    lesson_id: lessonId,
    results,
  });
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
