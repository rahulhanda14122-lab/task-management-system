import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";

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

export function MyTasksPage() {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [updatingId, setUpdatingId] = useState(null);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const { data } = await api.get("/tasks/my-eligible-tasks");
      setTasks(data.items);
    } catch {
      setError("Failed to load your tasks");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const setStatus = async (task, nextStatus) => {
    setUpdatingId(task.id);
    setError("");
    try {
      const { data } = await api.patch(`/tasks/${task.id}`, { status: nextStatus });
      setTasks((prev) => prev.map((t) => (t.id === task.id ? data : t)));
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to update status");
      await load();
    } finally {
      setUpdatingId(null);
    }
  };

  if (loading) return <div className="page-center">Loading...</div>;

  return (
    <div className="container">
      <div className="row-between">
        <h2>My Assigned Tasks</h2>
        <Link to="/pending">Browse pending tasks</Link>
      </div>
      {error && <p className="error">{error}</p>}
      {tasks.length === 0 ? (
        <p>
          No tasks assigned to you yet. Check{" "}
          <Link to="/pending">pending tasks</Link> you may be eligible to claim, or wait for
          automatic assignment.
        </p>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Title</th>
              <th>Priority</th>
              <th>Due Date</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {tasks.map((task) => (
              <tr key={task.id}>
                <td>
                  <Link to={`/tasks/${task.id}`}>
                    <strong>{task.title}</strong>
                  </Link>
                  <div className="muted">{task.description}</div>
                </td>
                <td>
                  <span className={`badge badge-${task.priority}`}>{task.priority}</span>
                </td>
                <td>{task.due_date || "-"}</td>
                <td>{STATUS_LABEL[task.status]}</td>
                <td>
                  <div className="action-row">
                    {(STATUS_ACTIONS[task.status] || []).map((action) => (
                      <button
                        key={action.next}
                        className={action.next === "todo" ? "btn-secondary" : undefined}
                        onClick={() => setStatus(task, action.next)}
                        disabled={updatingId === task.id}
                      >
                        {updatingId === task.id ? "Updating..." : action.label}
                      </button>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
