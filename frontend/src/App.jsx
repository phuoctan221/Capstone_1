import { useEffect, useState } from "react";
import { Routes, Route, Navigate, Outlet } from "react-router-dom";
import Navbar from "./components/Navbar";
import AdminLayout from "./components/AdminLayout";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import DashboardPage from "./pages/DashboardPage";
import ProgressPage from "./pages/ProgressPage";
import LearnPage from "./pages/LearnPage";
import LessonPage from "./pages/LessonPage";
import PracticePage from "./pages/PracticePage";
import QuizPage from "./pages/QuizPage";
import FlashcardsPage from "./pages/FlashcardPage";
import VocabularyPage from "./pages/VocabularyPage";
import AdminDashboardPage from "./pages/AdminDashboardPage";
import AdminUsersPage from "./pages/AdminUsersPage";
import AdminUserDetailPage from "./pages/AdminUserDetailPage";
import AdminPage from "./pages/AdminPage";
import AdminDomainsPage from "./pages/AdminDomainsPage";
import AdminLessonsPage from "./pages/AdminLessonsPage";
import AdminExercisesPage from "./pages/AdminExercisesPage";
import OnboardingLevelPage from "./pages/OnboardingLevelPage";
import OnboardingInterestsPage from "./pages/OnboardingInterestsPage";
import OnboardingSettingsPage from "./pages/OnboardingSettingsPage";
import ProfilePage from "./pages/ProfilePage";
import { getToken, fetchMe, clearSession } from "./services/authService";
import { isAdmin } from "./constants/domains";
import { useAuth } from "./hooks/useAuth";

function homeFor(user) {
  if (!user) return "/login";
  if (isAdmin(user)) return "/admin";
  if (user.onboarded === false) return "/onboarding/level";
  return "/dashboard";
}

function BootScreen() {
  return (
    <div style={{ minHeight: "100vh", display: "grid", placeItems: "center" }}>
      <div className="sv-center-state" style={{ minWidth: 320 }} role="status">
        <div className="sv-loader" />
        <p>Đang xác minh phiên đăng nhập...</p>
      </div>
    </div>
  );
}

function PublicOnly({ children }) {
  const user = useAuth();
  if (getToken() && user) return <Navigate to={homeFor(user)} replace />;
  return children;
}

function UserLayout() {
  const user = useAuth();
  if (!getToken() || !user) return <Navigate to="/login" replace />;
  if (isAdmin(user)) return <Navigate to="/admin" replace />;
  if (user.onboarded === false) return <Navigate to="/onboarding/level" replace />;
  return (
    <>
      <Navbar />
      <main className="container sv-app-main">
        <Outlet />
      </main>
    </>
  );
}

function AdminGuard() {
  const user = useAuth();
  if (!getToken() || !user) return <Navigate to="/login" replace />;
  if (!isAdmin(user)) return <Navigate to="/dashboard" replace />;
  return <AdminLayout />;
}

function OnboardingRoute({ children }) {
  const user = useAuth();
  if (!getToken() || !user) return <Navigate to="/login" replace />;
  if (isAdmin(user)) return <Navigate to="/admin" replace />;
  if (user.onboarded === true) return <Navigate to="/dashboard" replace />;
  return children;
}

function RootRedirect() {
  const user = useAuth();
  if (!getToken() || !user) return <Navigate to="/login" replace />;
  return <Navigate to={homeFor(user)} replace />;
}

export default function App() {
  const [booting, setBooting] = useState(() => Boolean(getToken()));

  useEffect(() => {
    if (!getToken()) {
      setBooting(false);
      return undefined;
    }
    let active = true;
    fetchMe()
      .catch(() => clearSession())
      .finally(() => {
        if (active) setBooting(false);
      });
    return () => {
      active = false;
    };
  }, []);

  if (booting) return <BootScreen />;

  return (
    <Routes>
      <Route path="/" element={<RootRedirect />} />
      <Route path="/login" element={<PublicOnly><LoginPage /></PublicOnly>} />
      <Route path="/register" element={<PublicOnly><RegisterPage /></PublicOnly>} />

      <Route path="/onboarding/level" element={<OnboardingRoute><OnboardingLevelPage /></OnboardingRoute>} />
      <Route path="/onboarding/interests" element={<OnboardingRoute><OnboardingInterestsPage /></OnboardingRoute>} />

      <Route element={<UserLayout />}>
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/learn" element={<LearnPage />} />
        <Route path="/progress" element={<ProgressPage />} />
        <Route path="/lessons/:lessonId" element={<LessonPage />} />
        <Route path="/lessons/:lessonId/practice/:skill" element={<PracticePage />} />
        <Route path="/lessons/:lessonId/quiz" element={<QuizPage />} />
        <Route path="/flashcards" element={<FlashcardsPage />} />
        <Route path="/vocabulary" element={<VocabularyPage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/settings/learning" element={<OnboardingSettingsPage />} />
      </Route>

      <Route path="/admin" element={<AdminGuard />}>
        <Route index element={<AdminDashboardPage />} />
        <Route path="users" element={<AdminUsersPage />} />
        <Route path="users/:id" element={<AdminUserDetailPage />} />
        <Route path="vocabulary" element={<AdminPage />} />
        <Route path="domains" element={<AdminDomainsPage />} />
        <Route path="lessons" element={<AdminLessonsPage />} />
        <Route path="exercises" element={<AdminExercisesPage />} />
      </Route>

      <Route path="/settings/onboarding" element={<Navigate to="/settings/learning" replace />} />
      <Route path="*" element={<RootRedirect />} />
    </Routes>
  );
}
