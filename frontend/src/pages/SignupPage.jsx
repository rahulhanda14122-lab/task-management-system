import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const DEPARTMENTS = ["finance", "hr", "it", "operations"];

export function SignupPage() {
  const { signup } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    email: "",
    password: "",
    full_name: "",
    department: "it",
    experience_years: 0,
    location: "",
  });
  const [error, setError] = useState("");

  const update = (field) => (e) =>
    setForm((prev) => ({ ...prev, [field]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    try {
      await signup({ ...form, experience_years: Number(form.experience_years) });
      navigate("/tasks");
    } catch (err) {
      setError(err.response?.data?.detail || "Signup failed");
    }
  };

  return (
    <div className="page-center">
      <form className="card" onSubmit={handleSubmit}>
        <h2>Sign up</h2>
        {error && <p className="error">{error}</p>}
        <label>
          Full name
          <input value={form.full_name} onChange={update("full_name")} required />
        </label>
        <label>
          Email
          <input value={form.email} onChange={update("email")} type="email" required />
        </label>
        <label>
          Password
          <input value={form.password} onChange={update("password")} type="password" minLength={8} required />
        </label>
        <label>
          Department
          <select value={form.department} onChange={update("department")}>
            {DEPARTMENTS.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </label>
        <label>
          Experience (years)
          <input value={form.experience_years} onChange={update("experience_years")} type="number" min={0} max={60} />
        </label>
        <label>
          Location
          <input value={form.location} onChange={update("location")} required />
        </label>
        <button type="submit">Create account</button>
        <p>
          Already have an account? <Link to="/login">Log in</Link>
        </p>
      </form>
    </div>
  );
}
