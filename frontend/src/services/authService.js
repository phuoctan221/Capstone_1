import api from "./api";

export function getToken() {
  return localStorage.getItem("token");
}

export function getUser() {
  const raw = localStorage.getItem("user");
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    localStorage.removeItem("user");
    return null;
  }
}

function emitAuthChange() {
  window.dispatchEvent(new Event("auth-change"));
}

export function setSession(token, user) {
  localStorage.setItem("token", token);
  localStorage.setItem("user", JSON.stringify(user));
  emitAuthChange();
}

export function clearSession() {
  localStorage.removeItem("token");
  localStorage.removeItem("user");
  emitAuthChange();
}

export async function login(email, password) {
  const { data } = await api.post("/auth/login", { email, password });
  setSession(data.access_token, data.user);
  return data;
}

export async function register(username, email, password) {
  const { data } = await api.post("/auth/register", {
    username,
    email,
    password,
  });
  setSession(data.access_token, data.user);
  return data;
}
