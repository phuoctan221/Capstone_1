import api from "./api";

export async function fetchDueCards() {
  const { data } = await api.get("/learning/due");
  return data;
}

export async function reviewCard(vocabularyId, remembered) {
  const { data } = await api.post("/learning/review", {
    vocabulary_id: vocabularyId,
    remembered,
  });
  return data;
}

export async function fetchStats() {
  const { data } = await api.get("/learning/stats");
  return data;
}
