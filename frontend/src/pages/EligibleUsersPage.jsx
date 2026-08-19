import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
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
      <h2>Eligible Users for: {task?.title}</h2>
      <p className="muted">
        Assignment status: <strong>{task?.assignment_status}</strong> | Currently assigned to user #
        {task?.assigned_to ?? "none"}
      </p>
      {users.length === 0 ? (
        <p>No eligible users currently match this task's rules. It will remain PENDING and is
          automatically retried whenever a user's profile changes, plus a periodic sweep.</p>
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
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className={u.id === task?.assigned_to ? "row-highlight" : ""}>
                <td>{u.full_name}</td>
                <td>{u.email}</td>
                <td>{u.department}</td>
                <td>{u.experience_years}</td>
                <td>{u.location}</td>
                <td>{u.active_task_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
