import { Navigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';

interface Props {
  children: React.ReactNode;
  require?: 'raid_leader' | 'officer';
}

export function ProtectedRoute({ children, require: req }: Props) {
  const { isAuthenticated, isRaidLeader, isOfficer } = useAuth();

  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (req === 'raid_leader' && !isRaidLeader) return <Navigate to="/dashboard" replace />;
  if (req === 'officer' && !isOfficer) return <Navigate to="/dashboard" replace />;

  return <>{children}</>;
}
