import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { login } from "../services/authService";
import "./LoginPage.css";

const DEMO_ACCOUNTS = [
  { label: "Demo User", email: "demo@smartvocab.com", password: "demo1234" },
  { label: "Test Student", email: "test@smartvocab.com", password: "test1234" },
];

export default function LoginPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: "", password: "" });
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const update = (event) => {
    setForm((previous) => ({ ...previous, [event.target.name]: event.target.value }));
    setError("");
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (loading) return;
    if (!form.email.trim() || !form.password) {
      setError("Vui lòng nhập email và mật khẩu.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      await login(form.email.trim(), form.password);
      navigate("/vocabulary");
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Không thể đăng nhập. Vui lòng kiểm tra thông tin và thử lại.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="auth-page">
      <section className="auth-shell" aria-labelledby="login-title">
        <div className="auth-intro">
          <Link className="auth-brand" to="/" aria-label="SmartVOCAB AI - Trang chủ"><span className="auth-brand-mark">SV</span> SmartVOCAB <span>AI</span></Link>
          <span className="auth-eyebrow">HỌC MỖI NGÀY, TIẾN BỘ MỖI NGÀY</span>
          <h1>Chào mừng bạn trở lại!</h1>
          <p>Tiếp tục hành trình chinh phục từ vựng tiếng Anh theo cách của riêng bạn.</p>
          <div className="auth-benefits"><span>✓ Học theo lộ trình</span><span>✓ Ôn tập thông minh</span><span>✓ Theo dõi tiến bộ</span></div>
        </div>
        <div className="auth-panel">
          <div className="auth-panel-head"><span className="auth-kicker">RẤT VUI KHI GẶP LẠI BẠN</span><h2 id="login-title">Đăng nhập</h2><p>Nhập thông tin để tiếp tục học nhé.</p></div>
          <form onSubmit={handleSubmit} noValidate>
            <div className="auth-field"><label htmlFor="login-email">Địa chỉ email</label><input id="login-email" name="email" type="email" placeholder="email@example.com" autoComplete="email" value={form.email} onChange={update} required /></div>
            <div className="auth-field"><label htmlFor="login-password">Mật khẩu</label><div className="auth-password"><input id="login-password" name="password" type={showPassword ? "text" : "password"} placeholder="Nhập mật khẩu" autoComplete="current-password" value={form.password} onChange={update} required /><button type="button" className="auth-show" onClick={() => setShowPassword((value) => !value)} aria-label={showPassword ? "Ẩn mật khẩu" : "Hiện mật khẩu"}>{showPassword ? "Ẩn" : "Hiện"}</button></div></div>
            {error && <p className="auth-error" role="alert">{error}</p>}
            <button className="auth-submit" type="submit" disabled={loading}>{loading ? "Đang đăng nhập..." : "Đăng nhập →"}</button>
          </form>
          <div className="auth-separator"><span>Hoặc dùng tài khoản demo</span></div>
          <div className="auth-demo-list">{DEMO_ACCOUNTS.map((account) => <div className="auth-demo" key={account.email}><div><strong>{account.label}</strong><small>{account.email}</small></div><button type="button" disabled={loading} onClick={() => { setForm({ email: account.email, password: account.password }); setError(""); }}>Điền nhanh</button></div>)}</div>
          <p className="auth-switch">Chưa có tài khoản? <Link to="/register">Đăng ký miễn phí</Link></p>
        </div>
      </section>
    </main>
  );
}
