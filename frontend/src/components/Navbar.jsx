import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export function Navbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <nav className="navbar">
      <div className="navbar-brand">Task Management System</div>
      <div className="navbar-links">
        <Link to="/tasks">My Tasks</Link>
        {(user?.role === "admin" || user?.role === "manager") && (
          <>
            <Link to="/admin/tasks">All Tasks</Link>
            <Link to="/admin/tasks/new">Create Task</Link>
          </>
        )}
        {user && (
          <span className="navbar-user">
            {user.full_name} ({user.role})
            <button onClick={handleLogout}>Logout</button>
          </span>
        )}
      </div>
    </nav>
  );
}
