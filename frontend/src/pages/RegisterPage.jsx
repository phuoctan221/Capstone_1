import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { register } from "../services/authService";

export default function RegisterPage() {
  const [form, setForm] = useState({ username: "", email: "", password: "" });
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    try {
      await register(form.username, form.email, form.password);
      navigate("/vocabulary");
    } catch (err) {
      setError(err.response?.data?.detail || "Đăng ký thất bại");
    }
  };

  return (
    <form className="card auth-card" onSubmit={handleSubmit}>
      <h2 style={{ marginBottom: "1rem" }}>Đăng ký</h2>
      <div className="form-group">
        <label>Tên đăng nhập</label>
        <input
          value={form.username}
          onChange={(e) => setForm({ ...form, username: e.target.value })}
          minLength={3}
          required
        />
      </div>
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
          minLength={6}
          required
        />
      </div>
      {error && <p className="error">{error}</p>}
      <button className="btn" type="submit" style={{ width: "100%" }}>
        Đăng ký
      </button>
      <p className="muted" style={{ marginTop: "1rem", textAlign: "center" }}>
        Đã có tài khoản? <Link to="/login">Đăng nhập</Link>
      </p>
    </form>
  );
}
