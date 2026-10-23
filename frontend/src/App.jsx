import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import Navbar from "./components/Navbar";
import HomePage from "./pages/HomePage";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import LearnPage from "./pages/LearnPage";
import LessonPage from "./pages/LessonPage";
import QuizPage from "./pages/QuizPage";
import FlashcardsPage from "./pages/FlashcardPage";
import VocabularyPage from "./pages/VocabularyPage";
import { getToken } from "./services/authService";

const AUTH_ROUTES = ["/login", "/register"];

function ProtectedRoute({ children }) {
  return getToken() ? children : <Navigate to="/login" replace />;
}

export default function App() {
  const location = useLocation();
  const isAuthenticated = Boolean(getToken());
  const isAuthPage = AUTH_ROUTES.includes(location.pathname);
  const showNavbar = isAuthenticated && !isAuthPage;

  return (
    <div className="app">
      {showNavbar && <Navbar />}
      <main className={showNavbar ? "container" : ""}>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
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
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
