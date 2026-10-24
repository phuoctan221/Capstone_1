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

export async function fetchMe() {
  const { data } = await api.get("/auth/me");
  const token = getToken();
  if (token) {
    setSession(token, data);
  } else {
    localStorage.setItem("user", JSON.stringify(data));
    emitAuthChange();
  }
  return data;
}

export async function refreshUser() {
  return fetchMe();
}

export async function updateProfile(payload) {
  const { data } = await api.put("/auth/me", payload);
  const token = getToken();
  if (token) {
    setSession(token, data);
  } else {
    localStorage.setItem("user", JSON.stringify(data));
    emitAuthChange();
  }
  return data;
}

export async function completeOnboarding(payload) {
  const { data } = await api.post("/auth/onboarding", payload);
  const token = getToken();
  if (token) {
    setSession(token, data);
  } else {
    localStorage.setItem("user", JSON.stringify(data));
    emitAuthChange();
  }
  return data;
}

export async function changePassword(payload) {
  const { data } = await api.put("/auth/password", payload);
  return data;
}
