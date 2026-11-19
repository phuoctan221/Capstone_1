import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { confirmPasswordReset, requestPasswordReset, verifyPasswordReset } from "../services/authService";
import { formatApiError } from "../constants/domains";
import "./LoginPage.css";

export default function ForgotPasswordPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [form, setForm] = useState({ email: "", otp: "", password: "", confirm: "" });
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const change = (event) => { setForm((old) => ({ ...old, [event.target.name]: event.target.value })); setError(""); };
  const submit = async (event) => {
    event.preventDefault(); if (loading) return;
    setError(""); setMessage(""); setLoading(true);
    try {
      if (step === 1) { await requestPasswordReset(form.email.trim()); setMessage("Nếu email đã đăng ký, mã xác minh đã được gửi. Kiểm tra cả thư rác."); setStep(2); }
      else if (step === 2) { await verifyPasswordReset(form.email.trim(), form.otp); setStep(3); }
      else { if (form.password !== form.confirm) throw new Error("Mật khẩu xác nhận không khớp."); await confirmPasswordReset(form.email.trim(), form.otp, form.password); navigate("/login", { replace: true, state: { resetSuccess: true } }); }
    } catch (err) { setError(err.message || formatApiError(err, "Không thể xử lý yêu cầu. Vui lòng thử lại.")); }
    finally { setLoading(false); }
  };
  const labels = ["Nhập email", "Xác minh mã", "Tạo mật khẩu mới"];
  return <main className="auth-page"><section className="auth-shell" aria-labelledby="forgot-title"><div className="auth-intro"><Link className="auth-brand" to="/"><span className="auth-brand-mark">SV</span> SmartVOCAB <span>AI</span></Link><span className="auth-eyebrow">KHÔI PHỤC TÀI KHOẢN</span><h1>Thiết lập lại mật khẩu an toàn.</h1><p>Mã 6 chữ số chỉ có hiệu lực trong thời gian ngắn và chỉ sử dụng được một lần.</p></div><div className="auth-panel"><div className="auth-panel-head"><span className="auth-kicker">BƯỚC {step}/3</span><h2 id="forgot-title">{labels[step - 1]}</h2><p>{step === 1 ? "Chúng tôi sẽ gửi mã xác minh đến email của bạn." : step === 2 ? "Nhập mã 6 chữ số trong email." : "Chọn mật khẩu mới có ít nhất 6 ký tự."}</p></div><form onSubmit={submit} noValidate>{step === 1 && <div className="auth-field"><label htmlFor="reset-email">Địa chỉ email</label><input id="reset-email" name="email" type="email" autoComplete="email" value={form.email} onChange={change} required /></div>}{step === 2 && <div className="auth-field"><label htmlFor="reset-otp">Mã xác minh</label><input id="reset-otp" name="otp" inputMode="numeric" maxLength={6} autoComplete="one-time-code" value={form.otp} onChange={change} required /></div>}{step === 3 && <><div className="auth-field"><label htmlFor="reset-password">Mật khẩu mới</label><input id="reset-password" name="password" type="password" minLength={6} autoComplete="new-password" value={form.password} onChange={change} required /></div><div className="auth-field"><label htmlFor="reset-confirm">Xác nhận mật khẩu</label><input id="reset-confirm" name="confirm" type="password" minLength={6} autoComplete="new-password" value={form.confirm} onChange={change} required /></div></>}{message && <p className="auth-message">{message}</p>}{error && <p className="auth-error" role="alert">{error}</p>}<button className="auth-submit" disabled={loading}>{loading ? "Đang xử lý..." : step === 3 ? "Đặt lại mật khẩu" : "Tiếp tục →"}</button></form><p className="auth-switch"><Link to="/login">Quay lại đăng nhập</Link></p></div></section></main>;
}