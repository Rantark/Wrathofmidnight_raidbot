import { AuthCallback } from '@/pages/AuthCallback';
import { useState } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { Sidebar } from '@/components/Layout/Sidebar';
import { MobileMenu } from '@/components/Layout/MobileMenu';
import { TopBar } from '@/components/Layout/TopBar';
import { ProtectedRoute } from '@/components/Layout/ProtectedRoute';
import { useAuth } from '@/contexts/AuthContext';

import { Login } from '@/pages/Login';
import { Dashboard } from '@/pages/Dashboard';
import { EventsList, EventDetail } from '@/pages/EventsList';
import { CharactersPage } from '@/pages/CharactersPage';
import { RosterView } from '@/pages/RosterView';
import { AttendancePage } from '@/pages/AttendancePage';
import { AdminPage } from '@/pages/AdminPage';
import { ChangelogPage } from '@/pages/ChangelogPage';

export default function App() {
  const [menuOpen, setMenuOpen] = useState(false);
  const { isAuthenticated } = useAuth();

  return (
    <div className="min-h-screen">
      {isAuthenticated && (
        <>
          <Sidebar />
          <TopBar onMenuOpen={() => setMenuOpen(true)} />
          <MobileMenu isOpen={menuOpen} onClose={() => setMenuOpen(false)} />
        </>
      )}

      <main className={isAuthenticated ? 'lg:pl-64 pt-14 lg:pt-0' : ''}>
        <Routes>
          <Route path="/login" element={<Login />} />

          <Route path="/dashboard" element={
            <ProtectedRoute><Dashboard /></ProtectedRoute>
          } />
          <Route path="/events" element={
            <ProtectedRoute><EventsList /></ProtectedRoute>
          } />
          <Route path="/events/:id" element={
            <ProtectedRoute><EventDetail /></ProtectedRoute>
          } />
          <Route path="/characters" element={
            <ProtectedRoute><CharactersPage /></ProtectedRoute>
          } />
          <Route path="/roster" element={
            <ProtectedRoute require="officer"><RosterView /></ProtectedRoute>
          } />
          <Route path="/attendance" element={
            <ProtectedRoute><AttendancePage /></ProtectedRoute>
          } />
          <Route path="/admin" element={
            <ProtectedRoute require="officer"><AdminPage /></ProtectedRoute>
          } />
          <Route path="/changelog" element={
            <ProtectedRoute><ChangelogPage /></ProtectedRoute>
          } />
          <Route path="/auth/callback" element={<AuthCallback />} />

          <Route path="*" element={
            isAuthenticated ? <Navigate to="/dashboard" replace /> : <Navigate to="/login" replace />
          } />
        </Routes>
      </main>
    </div>
  );
}
