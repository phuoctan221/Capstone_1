import api from "./api";

export function getToken() {
  return localStorage.getItem("token");
}

export function getUser() {
  const raw = localStorage.getItem("user");
  return raw ? JSON.parse(raw) : null;
}

export function setSession(token, user) {
  localStorage.setItem("token", token);
  localStorage.setItem("user", JSON.stringify(user));
}

export function clearSession() {
  localStorage.removeItem("token");
  localStorage.removeItem("user");
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
