import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";

const STATUS_ACTIONS = {
  todo: [{ next: "in_progress", label: "Mark In Progress" }],
  in_progress: [
    { next: "todo", label: "Move to Todo" },
    { next: "done", label: "Mark Done" },
  ],
};

const STATUS_LABEL = {
  todo: "Todo",
  in_progress: "In Progress",
  done: "Done",
};

export function TaskDetailPage() {
  const { taskId } = useParams();
  const { user } = useAuth();
  const [task, setTask] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const { data } = await api.get(`/tasks/${taskId}`);
      setTask(data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load task");
      setTask(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [taskId]);

  const setStatus = async (nextStatus) => {
    if (!task) return;
    setSaving(true);
    setError("");
    try {
      const { data } = await api.patch(`/tasks/${task.id}`, { status: nextStatus });
      setTask(data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to update status");
    } finally {
      setSaving(false);
    }
  };

  const claim = async () => {
    setSaving(true);
    setError("");
    try {
      const { data } = await api.post(`/tasks/${taskId}/claim`);
      setTask(data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to claim task");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="page-center">Loading...</div>;
  if (!task) {
    return (
      <div className="container">
        <p className="error">{error || "Task not found"}</p>
        <Link to="/tasks">Back to My Tasks</Link>
      </div>
    );
  }

  const isAssignee = task.assigned_to === user?.id;
  const isPrivileged = user?.role === "admin" || user?.role === "manager";
  const canChangeStatus = isAssignee || isPrivileged;
  const statusActions = canChangeStatus && task.status !== "done" ? STATUS_ACTIONS[task.status] || [] : [];
  const canClaim = task.assignment_status === "pending" && !task.assigned_to;

  return (
    <div className="container">
      <div className="row-between">
        <h2>{task.title}</h2>
        <div className="link-row">
          <Link to="/tasks">My Tasks</Link>
          <Link to="/pending">Pending</Link>
          {isPrivileged && <Link to="/admin/tasks">All Tasks</Link>}
        </div>
      </div>

      {error && <p className="error">{error}</p>}

      <div className="card">
        <p className="muted">{task.description || "No description"}</p>
        <div className="detail-grid">
          <div>
            <span className="muted">Priority</span>
            <div>
              <span className={`badge badge-${task.priority}`}>{task.priority}</span>
            </div>
          </div>
          <div>
            <span className="muted">Due date</span>
            <div>{task.due_date || "-"}</div>
          </div>
          <div>
            <span className="muted">Status</span>
            <div>{STATUS_LABEL[task.status] || task.status}</div>
          </div>
          <div>
            <span className="muted">Assignment</span>
            <div>
              <span className={`badge badge-${task.assignment_status}`}>{task.assignment_status}</span>
            </div>
          </div>
          <div>
            <span className="muted">Assigned to</span>
            <div>{task.assigned_to_name || "-"}</div>
          </div>
        </div>

        {task.rule && (
          <>
            <h3>Eligibility rules</h3>
            <div className="detail-grid">
              <div>
                <span className="muted">Department</span>
                <div>{task.rule.department || "(any)"}</div>
              </div>
              <div>
                <span className="muted">Min experience</span>
                <div>
                  {task.rule.min_experience_years === null || task.rule.min_experience_years === undefined
                    ? "(any)"
                    : `${task.rule.min_experience_years} yrs`}
                </div>
              </div>
              <div>
                <span className="muted">Location</span>
                <div>{task.rule.location || "(any)"}</div>
              </div>
              <div>
                <span className="muted">Max active tasks</span>
                <div>
                  {task.rule.max_active_tasks === null || task.rule.max_active_tasks === undefined
                    ? "(any)"
                    : task.rule.max_active_tasks}
                </div>
              </div>
            </div>
          </>
        )}

        <div className="action-row" style={{ marginTop: "1rem" }}>
          {statusActions.map((action) => (
            <button
              key={action.next}
              className={action.next === "todo" ? "btn-secondary" : undefined}
              onClick={() => setStatus(action.next)}
              disabled={saving}
            >
              {saving ? "Updating..." : action.label}
            </button>
          ))}
          {canClaim && (
            <button onClick={claim} disabled={saving}>
              Claim this task
            </button>
          )}
          {isPrivileged && task.status !== "done" && (
            <Link to={`/admin/tasks/${task.id}/edit`}>
              <button type="button">Edit (admin)</button>
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
