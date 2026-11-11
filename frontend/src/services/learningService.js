import api from "./api";

export async function fetchDueCards() {
  const { data } = await api.get("/learning/due");
  return data;
}

export async function reviewCard(vocabularyId, rating, reviewId) {
  const { data } = await api.post("/learning/review", {
    vocabulary_id: vocabularyId,
    rating,
    review_id: reviewId,
  });
  return data;
}

export async function fetchStats() {
  const { data } = await api.get("/learning/stats");
  return data;
}
