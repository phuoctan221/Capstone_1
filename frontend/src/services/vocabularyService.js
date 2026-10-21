import api from "./api";

export async function fetchVocabularies(params = {}) {
  const { data } = await api.get("/vocabulary", { params });
  return data;
}

export async function fetchVocabulary(id) {
  const { data } = await api.get(`/vocabulary/${id}`);
  return data;
}

export async function createVocabulary(payload) {
  const { data } = await api.post("/vocabulary", payload);
  return data;
}

export async function updateVocabulary(id, payload) {
  const { data } = await api.put(`/vocabulary/${id}`, payload);
  return data;
}

export async function deleteVocabulary(id) {
  await api.delete(`/vocabulary/${id}`);
}

export async function generateWithAI(word) {
  const { data } = await api.post("/vocabulary/ai-generate", {
    word,
    target_language: "vi",
  });
  return data;
}
