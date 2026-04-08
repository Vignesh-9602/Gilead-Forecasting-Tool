import React from 'react';
import { Routes, Route } from 'react-router-dom';
import ChatHistory from '../pages/chatHistory/ChatHistory';
import Header from '../pages/header/Header';
import LoginPage from '../pages/login/LoginPage';
import SnackbarNotification from '../components/snackbar/snackbar';
import ProtectedRoute from '../components/protectedRoute/ProtectedRoute';
import LoginCallback from '../pages/login/LoginCallBack';
import UnauthorizedPage from '../pages/chatHistory/UnauthorizedPage';
import LoggedOutPage from '../pages/logOut/LoggedOutPage';

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<LoginPage />} />
      <Route path="/login/callback" element={<LoginCallback />} />
      <Route path="/error/unauthorized" element={<UnauthorizedPage />} />
      <Route path="/logged-out" element={<LoggedOutPage />} />
      <Route
        path="/chat"
        element={
          <ProtectedRoute>
            <>
              <Header />
              <ChatHistory />
              <SnackbarNotification />
            </>
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}
