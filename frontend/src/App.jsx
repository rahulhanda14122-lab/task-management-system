import { Navigate, Route, Routes } from "react-router-dom";
import { Navbar } from "./components/Navbar";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { useAuth } from "./context/AuthContext";
import { AdminTasksPage } from "./pages/AdminTasksPage";
import { AdminUsersPage } from "./pages/AdminUsersPage";
import { CreateTaskPage } from "./pages/CreateTaskPage";
import { EditTaskPage } from "./pages/EditTaskPage";
import { EligibleUsersPage } from "./pages/EligibleUsersPage";
import { LoginPage } from "./pages/LoginPage";
import { MyTasksPage } from "./pages/MyTasksPage";
import { PendingTasksPage } from "./pages/PendingTasksPage";
import { ProfilePage } from "./pages/ProfilePage";
import { SignupPage } from "./pages/SignupPage";
import { TaskDetailPage } from "./pages/TaskDetailPage";
import { UserDetailPage } from "./pages/UserDetailPage";

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
          path="/tasks/:taskId"
          element={
            <ProtectedRoute>
              <TaskDetailPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/pending"
          element={
            <ProtectedRoute>
              <PendingTasksPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/profile"
          element={
            <ProtectedRoute>
              <ProfilePage />
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
          path="/admin/tasks/:taskId/edit"
          element={
            <ProtectedRoute roles={["admin", "manager"]}>
              <EditTaskPage />
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
        <Route
          path="/admin/users"
          element={
            <ProtectedRoute roles={["admin", "manager"]}>
              <AdminUsersPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/users/:userId"
          element={
            <ProtectedRoute roles={["admin", "manager"]}>
              <UserDetailPage />
            </ProtectedRoute>
          }
        />
        <Route path="*" element={<Navigate to="/tasks" replace />} />
      </Routes>
    </>
  );
}
