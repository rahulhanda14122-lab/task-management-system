import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";

const DEPARTMENTS = ["", "finance", "hr", "it", "operations"];
const PRIORITIES = ["low", "medium", "high"];

export function EditTaskPage() {
  const { taskId } = useParams();
  const navigate = useNavigate();
  const [form, setForm] = useState(null);
  const [taskMeta, setTaskMeta] = useState(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const { data } = await api.get(`/tasks/${taskId}`);
        setTaskMeta({
          id: data.id,
          assignment_status: data.assignment_status,
          assigned_to: data.assigned_to,
          assigned_to_name: data.assigned_to_name,
          status: data.status,
          rules_version: data.rules_version,
        });
        setForm({
          title: data.title || "",
          description: data.description || "",
          priority: data.priority || "medium",
          due_date: data.due_date || "",
          department: data.rule?.department || "",
          min_experience_years:
            data.rule?.min_experience_years === null || data.rule?.min_experience_years === undefined
              ? ""
              : String(data.rule.min_experience_years),
          location: data.rule?.location || "",
          max_active_tasks:
            data.rule?.max_active_tasks === null || data.rule?.max_active_tasks === undefined
              ? ""
              : String(data.rule.max_active_tasks),
        });
      } catch (err) {
        setError(err.response?.data?.detail || "Failed to load task");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [taskId]);

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
      const { data } = await api.patch(`/tasks/${taskId}`, payload);
      setSuccess(
        `Task #${data.id} updated. Eligibility recompute has been queued (assignment_status may briefly stay "${data.assignment_status}" until the worker finishes).`
      );
      setTimeout(() => navigate("/admin/tasks"), 1500);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to update task");
    }
  };

  if (loading) return <div className="page-center">Loading...</div>;
  if (!form) {
    return (
      <div className="container">
        <p className="error">{error || "Task not found"}</p>
        <Link to="/admin/tasks">Back to All Tasks</Link>
      </div>
    );
  }

  const isDone = taskMeta?.status === "done";

  return (
    <div className="container">
      <div className="row-between">
        <h2>{isDone ? `View Task #${taskId}` : `Edit Task #${taskId}`}</h2>
        <Link to="/admin/tasks">Back to All Tasks</Link>
      </div>

      {taskMeta && (
        <p className="muted">
          Status: <strong>{taskMeta.status}</strong> | Assignment:{" "}
          <strong>{taskMeta.assignment_status}</strong> | Assigned to:{" "}
          <strong>
            {taskMeta.assigned_to_name ? (
              <Link to={`/admin/users/${taskMeta.assigned_to}`}>{taskMeta.assigned_to_name}</Link>
            ) : (
              "none"
            )}
          </strong>{" "}
          | Rules version: <strong>{taskMeta.rules_version}</strong>
        </p>
      )}
      {isDone && (
        <p className="error">Completed tasks cannot be edited. This view is read-only.</p>
      )}
      {taskMeta?.status === "in_progress" && (
        <p className="muted">
          Note: this task is in progress and is locked to the current assignee. Recompute will run,
          but the assignee will not change until the task is back in <code>todo</code>.
        </p>
      )}

      <form className="card" onSubmit={isDone ? (e) => e.preventDefault() : handleSubmit}>
        {error && <p className="error">{error}</p>}
        {success && <p className="success">{success}</p>}
        <label>
          Title
          <input value={form.title} onChange={update("title")} required disabled={isDone} />
        </label>
        <label>
          Description
          <textarea value={form.description} onChange={update("description")} disabled={isDone} />
        </label>
        <div className="row">
          <label>
            Priority
            <select value={form.priority} onChange={update("priority")} disabled={isDone}>
              {PRIORITIES.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </label>
          <label>
            Due date
            <input type="date" value={form.due_date} onChange={update("due_date")} disabled={isDone} />
          </label>
        </div>

        <h3>Eligibility Rules</h3>
        <p className="muted">
          {isDone
            ? "Rules are shown for reference only."
            : "Saving always re-queues eligibility recompute. Leave a field blank to leave that attribute unconstrained."}
        </p>
        <div className="row">
          <label>
            Department
            <select value={form.department} onChange={update("department")} disabled={isDone}>
              {DEPARTMENTS.map((d) => (
                <option key={d} value={d}>
                  {d || "(any)"}
                </option>
              ))}
            </select>
          </label>
          <label>
            Min. experience (years)
            <input
              type="number"
              min={0}
              max={60}
              value={form.min_experience_years}
              onChange={update("min_experience_years")}
              disabled={isDone}
            />
          </label>
        </div>
        <div className="row">
          <label>
            Location
            <input
              value={form.location}
              onChange={update("location")}
              placeholder="(any)"
              disabled={isDone}
            />
          </label>
          <label>
            Max active tasks
            <input
              type="number"
              min={0}
              value={form.max_active_tasks}
              onChange={update("max_active_tasks")}
              disabled={isDone}
            />
          </label>
        </div>

        {!isDone && <button type="submit">Save &amp; Recompute</button>}
      </form>
    </div>
  );
}
