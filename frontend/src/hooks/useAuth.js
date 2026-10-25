import { useEffect, useState } from "react";
import { getUser } from "../services/authService";

export function useAuth() {
  const [user, setUser] = useState(() => getUser());

  useEffect(() => {
    const sync = () => setUser(getUser());
    window.addEventListener("auth-change", sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener("auth-change", sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  return user;
}
