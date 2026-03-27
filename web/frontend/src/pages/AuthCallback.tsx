import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';

export function AuthCallback() {
  const navigate = useNavigate();
  const { login } = useAuth();

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get('code');

    if (!code) {
      navigate('/login');
      return;
    }

    fetch(`/api/auth/discord/callback?code=${code}`)
      .then(res => res.json())
      .then(data => {
        if (data.token) {
          login(data.token, data.user);
          navigate('/dashboard');
        } else {
          navigate('/login');
        }
      })
      .catch(() => navigate('/login'));
  }, []);

  return (
    <div className="flex items-center justify-center min-h-screen">
      <p className="text-white">Logging you in...</p>
    </div>
  );
}
