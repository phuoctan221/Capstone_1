import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import api from "../services/api";
import { setSession } from "../services/authService";
import "./LoginPage.css";

export default function OAuthCallbackPage() {
  const { provider } = useParams();
  const navigate = useNavigate();
  const started = useRef(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    async function finish() {
      const params = new URLSearchParams(window.location.search);
      window.history.replaceState(null, "", window.location.pathname);
      try {
        if (provider !== "google") throw new Error("Phương thức đăng nhập không hợp lệ.");
        const pending = JSON.parse(sessionStorage.getItem("oauth-login") || "null");
        sessionStorage.removeItem("oauth-login");
        if (!pending || pending.provider !== provider || pending.state !== params.get("state")) {
          throw new Error("Phiên đăng nhập không hợp lệ. Vui lòng bắt đầu lại.");
        }
        if (params.has("error")) throw new Error("Đăng nhập đã bị hủy hoặc không được cấp quyền.");
        if (!params.get("code")) throw new Error("Không nhận được mã đăng nhập. Vui lòng thử lại.");
        const { data } = await api.post(`/auth/oauth/${provider}/exchange`, {
          code: params.get("code"), state: pending.state, browser_secret: pending.browser_secret,
        });
        setSession(data.access_token, data.user);
        navigate(data.user.onboarded ? "/learn" : "/onboarding/level", { replace: true });
      } catch (err) {
        const detail = err.response?.data?.detail;
        setError(typeof detail === "string" ? detail : err.message || "Đăng nhập thất bại. Vui lòng thử lại.");
      }
    }
    finish();
  }, [provider, navigate]);

  return (
    <main className="auth-page">
      <section className="auth-panel" aria-labelledby="oauth-title">
        <h1 id="oauth-title">Đăng nhập Google</h1>
        {error ? <><p className="auth-error" role="alert">{error}</p><Link to="/login">Quay lại đăng nhập</Link></> : <p role="status">Đang xác thực tài khoản…</p>}
      </section>
    </main>
  );
}
