import api from "./api";

const encode = (value) => encodeURIComponent(String(value));

export async function fetchAdminStats() {
  const { data } = await api.get("/admin/stats");
  return data;
}

export async function fetchAdminUsers(params = {}) {
  const { data } = await api.get("/admin/users", { params });
  return data;
}

export async function setUserRole(userId, role) {
  const { data } = await api.put(
    `/admin/users/${encode(userId)}/role`,
    { role },
  );
  return data;
}

export async function fetchAdminUser(userId) {
  const { data } = await api.get(`/admin/users/${encode(userId)}`);
  return data;
}

export async function updateAdminUser(userId, payload) {
  const { data } = await api.put(`/admin/users/${encode(userId)}`, payload);
  return data;
}

export async function deleteAdminUser(userId) {
  const { data } = await api.delete(`/admin/users/${encode(userId)}`);
  return data;
}

export async function resetAdminUserPassword(userId) {
  const { data } = await api.post(
    `/admin/users/${encode(userId)}/reset-password`,
  );
  return data;
}

export async function setAdminUserStatus(userId, isActive) {
  const { data } = await api.put(
    `/admin/users/${encode(userId)}/status`,
    { is_active: isActive },
  );
  return data;
}

export async function fetchAdminDomains() {
  const { data } = await api.get("/admin/domains");
  return data;
}

export async function updateAdminDomain(slug, payload) {
  const { data } = await api.put(`/admin/domains/${encode(slug)}`, payload);
  return data;
}

export async function ensureAdminDomains() {
  const { data } = await api.post("/admin/domains/ensure");
  return data;
}

export async function fetchAdminLessons() {
  const { data } = await api.get("/admin/lessons");
  return data;
}

export async function createAdminLesson(payload) {
  const { data } = await api.post("/admin/lessons", payload);
  return data;
}

export async function updateAdminLesson(lessonId, payload) {
  const { data } = await api.put(
    `/admin/lessons/${encode(lessonId)}`,
    payload,
  );
  return data;
}

export async function deleteAdminLesson(lessonId) {
  await api.delete(`/admin/lessons/${encode(lessonId)}`);
}

export async function fetchAdminLessonWords(lessonId, params = {}) {
  const { data } = await api.get(
    `/admin/lessons/${encode(lessonId)}/words`,
    { params },
  );
  return data;
}

export async function fetchAdminExercises(params = {}) {
  const { data } = await api.get("/admin/exercises", { params });
  return data;
}

export async function fetchAdminExercise(itemId) {
  const { data } = await api.get(`/admin/exercises/${encode(itemId)}`);
  return data;
}

export async function createAdminExercise(payload) {
  const { data } = await api.post("/admin/exercises", payload);
  return data;
}

export async function updateAdminExercise(itemId, payload) {
  const { data } = await api.put(
    `/admin/exercises/${encode(itemId)}`,
    payload,
  );
  return data;
}

export async function deleteAdminExercise(itemId) {
  await api.delete(`/admin/exercises/${encode(itemId)}`);
}

export async function regenerateAdminExercises(lessonId) {
  const { data } = await api.post("/admin/exercises/regenerate", null, {
    params: { lesson_id: lessonId },
  });
  return data;
}

export async function fetchAdminVocabularies(params = {}) {
  const { data } = await api.get("/admin/vocabularies", { params });
  return data;
}

export async function createAdminVocabulary(payload) {
  const { data } = await api.post("/admin/vocabularies", payload);
  return data;
}

export async function updateAdminVocabulary(vocabId, payload) {
  const { data } = await api.put(
    `/admin/vocabularies/${encode(vocabId)}`,
    payload,
  );
  return data;
}

export async function deleteAdminVocabulary(vocabId) {
  await api.delete(`/admin/vocabularies/${encode(vocabId)}`);
}
