import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";

export function PendingTasksPage() {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [claimingId, setClaimingId] = useState(null);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const { data } = await api.get("/tasks/pending");
      setTasks(data.items);
    } catch {
      setError("Failed to load pending tasks");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const claim = async (taskId) => {
    setClaimingId(taskId);
    setError("");
    try {
      await api.post(`/tasks/${taskId}/claim`);
      await load();
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to claim task");
    } finally {
      setClaimingId(null);
    }
  };

  if (loading) return <div className="page-center">Loading...</div>;

  return (
    <div className="container">
      <div className="row-between">
        <h2>Pending (unassigned) tasks</h2>
        <button onClick={load}>Refresh</button>
      </div>
      <p className="muted">
        These tasks have no assignee yet. If you match the rules (and are under the active-task
        limit), you can claim them yourself.
      </p>
      {error && <p className="error">{error}</p>}
      {tasks.length === 0 ? (
        <p>No pending tasks match your view right now.</p>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Title</th>
              <th>Priority</th>
              <th>Due</th>
              <th>Rules</th>
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
                <td className="muted">
                  {[
                    task.rule?.department,
                    task.rule?.min_experience_years != null
                      ? `≥${task.rule.min_experience_years}y`
                      : null,
                    task.rule?.location,
                  ]
                    .filter(Boolean)
                    .join(" · ") || "(open)"}
                </td>
                <td>
                  {task.can_claim ? (
                    <button onClick={() => claim(task.id)} disabled={claimingId === task.id}>
                      {claimingId === task.id ? "Claiming..." : "Assign to me"}
                    </button>
                  ) : (
                    <span className="muted">Not eligible / at capacity</span>
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
