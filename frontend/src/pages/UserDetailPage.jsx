import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";

const DEPARTMENTS = ["finance", "hr", "it", "operations"];

const STATUS_LABEL = {
  todo: "Todo",
  in_progress: "In Progress",
  done: "Done",
};

export function UserDetailPage() {
  const { userId } = useParams();
  const { user: me } = useAuth();
  const isAdmin = me?.role === "admin";

  const [profile, setProfile] = useState(null);
  const [form, setForm] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [userRes, tasksRes] = await Promise.all([
        api.get(`/users/${userId}`),
        api.get(`/users/${userId}/tasks`),
      ]);
      setProfile(userRes.data);
      setForm({
        full_name: userRes.data.full_name || "",
        department: userRes.data.department || "it",
        experience_years: String(userRes.data.experience_years ?? 0),
        location: userRes.data.location || "",
        is_active: userRes.data.is_active,
      });
      setTasks(tasksRes.data.items);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load user");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [userId]);

  const update = (field) => (e) => {
    const value = field === "is_active" ? e.target.checked : e.target.value;
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!isAdmin) return;
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const { data } = await api.patch(`/users/${userId}`, {
        full_name: form.full_name,
        department: form.department,
        experience_years: Number(form.experience_years),
        location: form.location,
        is_active: form.is_active,
      });
      setProfile(data);
      setSuccess(
        "User updated. Eligibility recompute has been queued if department, experience, location, or active status changed."
      );
      setTimeout(load, 800);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to update user");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="page-center">Loading...</div>;
  if (!profile || !form) {
    return (
      <div className="container">
        <p className="error">{error || "User not found"}</p>
        <Link to="/admin/users">Back to Users</Link>
      </div>
    );
  }

  return (
    <div className="container">
      <div className="row-between">
        <h2>{profile.full_name}</h2>
        <Link to="/admin/users">Back to Users</Link>
      </div>

      <form className="card" onSubmit={handleSubmit}>
        {error && <p className="error">{error}</p>}
        {success && <p className="success">{success}</p>}
        <label>
          Email
          <input value={profile.email} disabled />
        </label>
        <label>
          Role
          <input value={profile.role} disabled />
        </label>
        <label>
          Full name
          <input
            value={form.full_name}
            onChange={update("full_name")}
            required
            disabled={!isAdmin}
          />
        </label>
        <div className="row">
          <label>
            Department
            <select value={form.department} onChange={update("department")} disabled={!isAdmin}>
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
              disabled={!isAdmin}
              required
            />
          </label>
        </div>
        <label>
          Location
          <input value={form.location} onChange={update("location")} disabled={!isAdmin} required />
        </label>
        <label className="checkbox-row">
          <input
            type="checkbox"
            checked={form.is_active}
            onChange={update("is_active")}
            disabled={!isAdmin}
          />
          Active account
        </label>
        <p className="muted">Active task count: {profile.active_task_count}</p>
        {isAdmin ? (
          <button type="submit" disabled={saving}>
            {saving ? "Saving..." : "Save & Recompute"}
          </button>
        ) : (
          <p className="muted">Only admins can edit user parameters.</p>
        )}
      </form>

      <h3 style={{ marginTop: "2rem" }}>Assigned tasks</h3>
      {tasks.length === 0 ? (
        <p className="muted">No tasks currently assigned to this user.</p>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Title</th>
              <th>Status</th>
              <th>Assignment</th>
              <th>Priority</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {tasks.map((task) => (
              <tr key={task.id}>
                <td>
                  <Link to={`/tasks/${task.id}`}>{task.title}</Link>
                </td>
                <td>{STATUS_LABEL[task.status] || task.status}</td>
                <td>{task.assignment_status}</td>
                <td>
                  <span className={`badge badge-${task.priority}`}>{task.priority}</span>
                </td>
                <td>
                  {isAdmin && task.status !== "done" && (
                    <Link to={`/admin/tasks/${task.id}/edit`}>Edit task</Link>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
