import { Navigate, Route, Routes } from "react-router-dom";
import { Navbar } from "./components/Navbar";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { useAuth } from "./context/AuthContext";
import { AdminTasksPage } from "./pages/AdminTasksPage";
import { CreateTaskPage } from "./pages/CreateTaskPage";
import { EligibleUsersPage } from "./pages/EligibleUsersPage";
import { LoginPage } from "./pages/LoginPage";
import { MyTasksPage } from "./pages/MyTasksPage";
import { SignupPage } from "./pages/SignupPage";

export default function App() {
  const { user } = useAuth();

  return (
    <>
      {user && <Navbar />}
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route
          path="/tasks"
          element={
            <ProtectedRoute>
              <MyTasksPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/tasks"
          element={
            <ProtectedRoute roles={["admin", "manager"]}>
              <AdminTasksPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/tasks/new"
          element={
            <ProtectedRoute roles={["admin", "manager"]}>
              <CreateTaskPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/tasks/:taskId/eligible-users"
          element={
            <ProtectedRoute roles={["admin", "manager"]}>
              <EligibleUsersPage />
            </ProtectedRoute>
          }
        />
        <Route path="*" element={<Navigate to="/tasks" replace />} />
      </Routes>
    </>
  );
}
