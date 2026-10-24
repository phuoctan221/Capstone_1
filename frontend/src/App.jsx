import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import Navbar from "./components/Navbar";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import LearnPage from "./pages/LearnPage";
import LessonPage from "./pages/LessonPage";
import QuizPage from "./pages/QuizPage";
import FlashcardsPage from "./pages/FlashcardPage";
import VocabularyPage from "./pages/VocabularyPage";
import OnboardingLevelPage from "./pages/OnboardingLevelPage";
import OnboardingInterestsPage from "./pages/OnboardingInterestsPage";
import OnboardingSettingsPage from "./pages/OnboardingSettingsPage";
import ProfilePage from "./pages/ProfilePage";
import { getToken, getUser } from "./services/authService";

const AUTH_ROUTES = ["/login", "/register"];

function ProtectedRoute({ children }) {
  if (!getToken()) return <Navigate to="/login" replace />;
  const user = getUser();
  if (user && user.onboarded === false) {
    return <Navigate to="/onboarding/level" replace />;
  }
  return children;
}

function OnboardingRoute({ children }) {
  if (!getToken()) return <Navigate to="/login" replace />;
  const user = getUser();
  if (user && user.onboarded === true) {
    return <Navigate to="/learn" replace />;
  }
  return children;
}

export default function App() {
  const location = useLocation();
  const isAuthenticated = Boolean(getToken());
  const user = getUser();
  const needsOnboarding = isAuthenticated && user && user.onboarded === false;
  const isAuthPage = AUTH_ROUTES.includes(location.pathname);
  const isOnboardingPage = location.pathname.startsWith("/onboarding");
  const showNavbar = isAuthenticated && !isAuthPage && !isOnboardingPage;

  return (
    <div className="app">
      {showNavbar && <Navbar />}
      <main className={showNavbar ? "container" : ""}>
        <Routes>
          <Route
            path="/"
            element={
              <Navigate
                to={
                  !isAuthenticated
                    ? "/login"
                    : needsOnboarding
                      ? "/onboarding/level"
                      : "/learn"
                }
                replace
              />
            }
          />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route
            path="/onboarding/level"
            element={
              <OnboardingRoute>
                <OnboardingLevelPage />
              </OnboardingRoute>
            }
          />
          <Route
            path="/onboarding/interests"
            element={
              <OnboardingRoute>
                <OnboardingInterestsPage />
              </OnboardingRoute>
            }
          />
          <Route path="/settings/onboarding" element={<Navigate to="/settings/learning" replace />} />
          <Route
            path="/settings/learning"
            element={
              <ProtectedRoute>
                <OnboardingSettingsPage />
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
            path="/learn"
            element={
              <ProtectedRoute>
                <LearnPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/lessons/:lessonId"
            element={
              <ProtectedRoute>
                <LessonPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/lessons/:lessonId/quiz"
            element={
              <ProtectedRoute>
                <QuizPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/flashcards"
            element={
              <ProtectedRoute>
                <FlashcardsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/vocabulary"
            element={
              <ProtectedRoute>
                <VocabularyPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="*"
            element={
              <Navigate
                to={
                  !isAuthenticated
                    ? "/login"
                    : needsOnboarding
                      ? "/onboarding/level"
                      : "/learn"
                }
                replace
              />
            }
          />
        </Routes>
      </main>
    </div>
  );
}
