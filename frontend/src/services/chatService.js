import api from "./api";

export async function sendChatMessage(payload) {
  const { data } = await api.post("/chat/messages", payload);
  return data;
}