import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";

export function EligibleUsersPage() {
  const { taskId } = useParams();
  const [users, setUsers] = useState([]);
  const [task, setTask] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    const [taskRes, usersRes] = await Promise.all([
      api.get(`/tasks/${taskId}`),
      api.get(`/tasks/${taskId}/eligible-users`),
    ]);
    setTask(taskRes.data);
    setUsers(usersRes.data);
    setLoading(false);
  };

  useEffect(() => {
    load();
  }, [taskId]);

  if (loading) return <div className="page-center">Loading...</div>;

  return (
    <div className="container">
      <div className="row-between">
        <h2>Eligible Users for: {task?.title}</h2>
        <Link to="/admin/tasks">Back to All Tasks</Link>
      </div>
      <p className="muted">
        Assignment status: <strong>{task?.assignment_status}</strong> | Currently assigned to{" "}
        <strong>{task?.assigned_to_name || "none"}</strong>
      </p>
      {users.length === 0 ? (
        <p>
          No eligible users currently match this task&apos;s rules. It will remain PENDING and is
          automatically retried whenever a user&apos;s profile changes, plus a periodic sweep.
        </p>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Email</th>
              <th>Department</th>
              <th>Experience</th>
              <th>Location</th>
              <th>Active Tasks</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr
                key={u.id}
                className={u.is_current_assignee || u.id === task?.assigned_to ? "row-highlight" : ""}
              >
                <td>
                  <Link to={`/admin/users/${u.id}`}>{u.full_name}</Link>
                  {(u.is_current_assignee || u.id === task?.assigned_to) && (
                    <span className="badge badge-assigned" style={{ marginLeft: "0.5rem" }}>
                      Assigned
                    </span>
                  )}
                </td>
                <td>{u.email}</td>
                <td>{u.department}</td>
                <td>{u.experience_years}</td>
                <td>{u.location}</td>
                <td>{u.active_task_count}</td>
                <td>
                  <Link to={`/admin/users/${u.id}`}>Edit user</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
