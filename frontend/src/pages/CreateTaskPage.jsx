import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";

const DEPARTMENTS = ["", "finance", "hr", "it", "operations"];
const PRIORITIES = ["low", "medium", "high"];

export function CreateTaskPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    title: "",
    description: "",
    priority: "medium",
    due_date: "",
    department: "",
    min_experience_years: "",
    location: "",
    max_active_tasks: "",
  });
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const update = (field) => (e) => setForm((prev) => ({ ...prev, [field]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    try {
      const payload = {
        title: form.title,
        description: form.description || null,
        priority: form.priority,
        due_date: form.due_date || null,
        rules: {
          department: form.department || null,
          min_experience_years: form.min_experience_years === "" ? null : Number(form.min_experience_years),
          location: form.location || null,
          max_active_tasks: form.max_active_tasks === "" ? null : Number(form.max_active_tasks),
        },
      };
      const { data } = await api.post("/tasks/", payload);
      setSuccess(`Task #${data.id} created with status "${data.assignment_status}". Assignment runs in the background.`);
      setTimeout(() => navigate("/admin/tasks"), 1500);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to create task");
    }
  };

  return (
    <div className="container">
      <h2>Create Task with Dynamic Assignment Rules</h2>
      <form className="card" onSubmit={handleSubmit}>
        {error && <p className="error">{error}</p>}
        {success && <p className="success">{success}</p>}
        <label>
          Title
          <input value={form.title} onChange={update("title")} required />
        </label>
        <label>
          Description
          <textarea value={form.description} onChange={update("description")} />
        </label>
        <div className="row">
          <label>
            Priority
            <select value={form.priority} onChange={update("priority")}>
              {PRIORITIES.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </label>
          <label>
            Due date
            <input type="date" value={form.due_date} onChange={update("due_date")} />
          </label>
        </div>

        <h3>Eligibility Rules</h3>
        <p className="muted">Leave a field blank to leave that attribute unconstrained.</p>
        <div className="row">
          <label>
            Department
            <select value={form.department} onChange={update("department")}>
              {DEPARTMENTS.map((d) => (
                <option key={d} value={d}>
                  {d || "(any)"}
                </option>
              ))}
            </select>
          </label>
          <label>
            Min. experience (years)
            <input type="number" min={0} max={60} value={form.min_experience_years} onChange={update("min_experience_years")} />
          </label>
        </div>
        <div className="row">
          <label>
            Location
            <input value={form.location} onChange={update("location")} placeholder="(any)" />
          </label>
          <label>
            Max active tasks
            <input type="number" min={0} value={form.max_active_tasks} onChange={update("max_active_tasks")} />
          </label>
        </div>

        <button type="submit">Create Task</button>
      </form>
    </div>
  );
}
