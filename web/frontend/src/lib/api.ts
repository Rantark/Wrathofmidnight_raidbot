import axios from 'axios';

const BASE_URL = import.meta.env.VITE_API_URL ?? '';

export const api = axios.create({
  baseURL: BASE_URL,
  timeout: 15000,
});

// Attach JWT on every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('jwt_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// If 401, clear token and reload to login
api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('jwt_token');
      window.location.href = '/login';
    }
    return Promise.reject(err);
  }
);
