import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";

const DEPARTMENTS = ["finance", "hr", "it", "operations"];

export function ProfilePage() {
  const { user, refreshUser } = useAuth();
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!user) return;
    setForm({
      full_name: user.full_name || "",
      department: user.department || "it",
      experience_years: String(user.experience_years ?? 0),
      location: user.location || "",
    });
  }, [user]);

  const update = (field) => (e) => setForm((prev) => ({ ...prev, [field]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    setSaving(true);
    try {
      const { data } = await api.patch("/users/me", {
        full_name: form.full_name,
        department: form.department,
        experience_years: Number(form.experience_years),
        location: form.location,
      });
      await refreshUser();
      setSuccess(
        `Profile saved. If department, experience, or location changed, eligibility recompute was queued for ${data.full_name}.`
      );
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to update profile");
    } finally {
      setSaving(false);
    }
  };

  if (!form) return <div className="page-center">Loading...</div>;

  return (
    <div className="container">
      <h2>My Profile</h2>
      <p className="muted">
        Update your details below. Changing department, experience, or location may reassign
        eligible todo tasks and unlock matching pending work.
      </p>
      <form className="card" onSubmit={handleSubmit}>
        {error && <p className="error">{error}</p>}
        {success && <p className="success">{success}</p>}
        <label>
          Email
          <input value={user?.email || ""} disabled />
        </label>
        <label>
          Role
          <input value={user?.role || ""} disabled />
        </label>
        <label>
          Full name
          <input value={form.full_name} onChange={update("full_name")} required />
        </label>
        <div className="row">
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
            <input
              type="number"
              min={0}
              max={60}
              value={form.experience_years}
              onChange={update("experience_years")}
              required
            />
          </label>
        </div>
        <label>
          Location
          <input value={form.location} onChange={update("location")} required />
        </label>
        <p className="muted">Active tasks: {user?.active_task_count ?? 0}</p>
        <button type="submit" disabled={saving}>
          {saving ? "Saving..." : "Save profile"}
        </button>
      </form>
    </div>
  );
}
