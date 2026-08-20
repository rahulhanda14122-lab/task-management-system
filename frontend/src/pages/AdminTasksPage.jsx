import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";

const ASSIGNMENT_BADGE = {
  pending: "badge-pending",
  assigned: "badge-assigned",
  unassignable: "badge-unassignable",
};

export function AdminTasksPage() {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    const { data } = await api.get("/tasks/");
    setTasks(data.items);
    setLoading(false);
  };

  useEffect(() => {
    load();
  }, []);

  const triggerRecompute = async (taskId) => {
    await api.post("/tasks/recompute-eligibility", { task_id: taskId });
    setTimeout(load, 1000);
  };

  if (loading) return <div className="page-center">Loading...</div>;

  return (
    <div className="container">
      <div className="row-between">
        <h2>All Tasks</h2>
        <Link to="/admin/tasks/new">
          <button>+ Create Task</button>
        </Link>
      </div>
      <table className="table">
        <thead>
          <tr>
            <th>Title</th>
            <th>Status</th>
            <th>Assignment</th>
            <th>Assigned To</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {tasks.map((task) => (
            <tr key={task.id}>
              <td>{task.title}</td>
              <td>{task.status}</td>
              <td>
                <span className={`badge ${ASSIGNMENT_BADGE[task.assignment_status]}`}>
                  {task.assignment_status}
                </span>
              </td>
              <td>
                {task.assigned_to_name ? (
                  <Link to={`/admin/users/${task.assigned_to}`}>{task.assigned_to_name}</Link>
                ) : (
                  "-"
                )}
              </td>
              <td>
                <Link to={`/tasks/${task.id}`}>View</Link>
                {" | "}
                {task.status !== "done" && (
                  <>
                    <Link to={`/admin/tasks/${task.id}/edit`}>Edit</Link>
                    {" | "}
                  </>
                )}
                <Link to={`/admin/tasks/${task.id}/eligible-users`}>Eligible users</Link>
                {" | "}
                <button onClick={() => triggerRecompute(task.id)}>Recompute</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
