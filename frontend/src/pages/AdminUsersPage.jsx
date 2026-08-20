import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";

export function AdminUsersPage() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const { data } = await api.get("/users/");
        setUsers(data.items);
      } catch {
        setError("Failed to load users");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  if (loading) return <div className="page-center">Loading...</div>;

  return (
    <div className="container">
      <h2>Users</h2>
      <p className="muted">Click a user to view assigned tasks and edit profile parameters.</p>
      {error && <p className="error">{error}</p>}
      <table className="table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Email</th>
            <th>Role</th>
            <th>Department</th>
            <th>Experience</th>
            <th>Location</th>
            <th>Active tasks</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id}>
              <td>
                <Link to={`/admin/users/${u.id}`}>{u.full_name}</Link>
              </td>
              <td>{u.email}</td>
              <td>{u.role}</td>
              <td>{u.department}</td>
              <td>{u.experience_years}</td>
              <td>{u.location}</td>
              <td>{u.active_task_count}</td>
              <td>
                <Link to={`/admin/users/${u.id}`}>View / Edit</Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
