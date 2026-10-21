import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { login } from "../services/authService";

export default function LoginPage() {
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    try {
      await login(form.email, form.password);
      navigate("/vocabulary");
    } catch (err) {
      setError(err.response?.data?.detail || "Đăng nhập thất bại");
    }
  };

  return (
    <form className="card auth-card" onSubmit={handleSubmit}>
      <h2 style={{ marginBottom: "1rem" }}>Đăng nhập</h2>
      <div className="form-group">
        <label>Email</label>
        <input
          type="email"
          value={form.email}
          onChange={(e) => setForm({ ...form, email: e.target.value })}
          required
        />
      </div>
      <div className="form-group">
        <label>Mật khẩu</label>
        <input
          type="password"
          value={form.password}
          onChange={(e) => setForm({ ...form, password: e.target.value })}
          required
        />
      </div>
      {error && <p className="error">{error}</p>}
      <button className="btn" type="submit" style={{ width: "100%" }}>
        Đăng nhập
      </button>
      <p className="muted" style={{ marginTop: "1rem", textAlign: "center" }}>
        Chưa có tài khoản? <Link to="/register">Đăng ký</Link>
      </p>
    </form>
  );
}
