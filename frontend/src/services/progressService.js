import api from "./api";

export async function fetchMasterySummary() {
  const { data } = await api.get("/progress/mastery");
  return data;
}

export async function fetchProgressHistory() {
  const { data } = await api.get("/progress/history");
  return data;
}
