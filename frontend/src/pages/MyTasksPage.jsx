import { useEffect, useState } from "react";
import { api } from "../api/client";

const STATUS_FLOW = {
  todo: "in_progress",
  in_progress: "done",
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

  const load = async () => {
    setLoading(true);
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

  const advanceStatus = async (task) => {
    const nextStatus = STATUS_FLOW[task.status];
    if (!nextStatus) return;
    await api.patch(`/tasks/${task.id}`, { status: nextStatus });
    load();
  };

  if (loading) return <div className="page-center">Loading...</div>;

  return (
    <div className="container">
      <h2>My Eligible / Assigned Tasks</h2>
      {error && <p className="error">{error}</p>}
      {tasks.length === 0 ? (
        <p>No tasks assigned to you yet. Tasks are auto-assigned in the background once you match a task's rules.</p>
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
                  <strong>{task.title}</strong>
                  <div className="muted">{task.description}</div>
                </td>
                <td>
                  <span className={`badge badge-${task.priority}`}>{task.priority}</span>
                </td>
                <td>{task.due_date || "-"}</td>
                <td>{STATUS_LABEL[task.status]}</td>
                <td>
                  {STATUS_FLOW[task.status] && (
                    <button onClick={() => advanceStatus(task)}>
                      Mark {STATUS_LABEL[STATUS_FLOW[task.status]]}
                    </button>
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
