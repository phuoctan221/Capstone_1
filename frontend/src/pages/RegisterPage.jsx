import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { register } from "../services/authService";
import "./LoginPage.css";

export default function RegisterPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ username: "", email: "", password: "" });
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
    if (form.username.trim().length < 3) return setError("Tên đăng nhập cần ít nhất 3 ký tự.");
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) return setError("Vui lòng nhập email hợp lệ.");
    if (form.password.length < 6) return setError("Mật khẩu cần ít nhất 6 ký tự.");
    setLoading(true);
    setError("");
    try {
      await register(form.username.trim(), form.email.trim(), form.password);
      navigate("/onboarding/level");
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Không thể đăng ký. Vui lòng thử lại.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="auth-page">
      <section className="auth-shell" aria-labelledby="register-title">
        <div className="auth-intro">
          <Link className="auth-brand" to="/" aria-label="SmartVOCAB AI - Trang chủ"><span className="auth-brand-mark">SV</span> SmartVOCAB <span>AI</span></Link>
          <span className="auth-eyebrow">BẮT ĐẦU HÀNH TRÌNH CỦA BẠN</span>
          <h1>Mỗi từ mới là một bước tiến.</h1>
          <p>Tạo tài khoản miễn phí để lưu từ vựng, luyện tập và theo dõi tiến độ học tập.</p>
          <div className="auth-benefits"><span>✓ 4 chế độ luyện tập</span><span>✓ Tích XP mỗi ngày</span><span>✓ Ôn tập theo Leitner</span></div>
        </div>
        <div className="auth-panel">
          <div className="auth-panel-head"><span className="auth-kicker">BẮT ĐẦU MIỄN PHÍ</span><h2 id="register-title">Tạo tài khoản</h2><p>Chỉ mất một phút để bắt đầu học.</p></div>
          <form onSubmit={handleSubmit} noValidate>
            <div className="auth-field"><label htmlFor="register-username">Tên đăng nhập</label><input id="register-username" name="username" placeholder="Ví dụ: minhnguyen" autoComplete="username" minLength={3} value={form.username} onChange={update} required /><small>Ít nhất 3 ký tự</small></div>
            <div className="auth-field"><label htmlFor="register-email">Địa chỉ email</label><input id="register-email" name="email" type="email" placeholder="email@example.com" autoComplete="email" value={form.email} onChange={update} required /></div>
            <div className="auth-field"><label htmlFor="register-password">Mật khẩu</label><div className="auth-password"><input id="register-password" name="password" type={showPassword ? "text" : "password"} placeholder="Tối thiểu 6 ký tự" autoComplete="new-password" minLength={6} value={form.password} onChange={update} required /><button type="button" className="auth-show" onClick={() => setShowPassword((value) => !value)} aria-label={showPassword ? "Ẩn mật khẩu" : "Hiện mật khẩu"}>{showPassword ? "Ẩn" : "Hiện"}</button></div><small>Nên kết hợp chữ, số và ký tự đặc biệt.</small></div>
            {error && <p className="auth-error" role="alert">{error}</p>}
            <button className="auth-submit" type="submit" disabled={loading}>{loading ? "Đang tạo tài khoản..." : "Đăng ký miễn phí →"}</button>
          </form>
          <p className="auth-switch">Đã có tài khoản? <Link to="/login">Đăng nhập</Link></p>
        </div>
      </section>
    </main>
  );
}
