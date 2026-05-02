// services/api.ts — Axios client with JWT auto-refresh
import axios, { AxiosInstance, InternalAxiosRequestConfig } from 'axios';
import * as SecureStore from 'expo-secure-store';

// ── Change this to your Render URL for production ──────────────────────────
export const API_BASE = __DEV__
  ? 'http://192.168.1.100:5000/api/v1'    // ← Replace with your local IP when testing
  : 'https://csmss-college-erp.onrender.com/api/v1';

const TOKEN_KEY   = 'csmss_access_token';
const REFRESH_KEY = 'csmss_refresh_token';

export const saveTokens = async (access: string, refresh: string) => {
  await SecureStore.setItemAsync(TOKEN_KEY,   access);
  await SecureStore.setItemAsync(REFRESH_KEY, refresh);
};

export const clearTokens = async () => {
  await SecureStore.deleteItemAsync(TOKEN_KEY);
  await SecureStore.deleteItemAsync(REFRESH_KEY);
};

export const getAccessToken  = () => SecureStore.getItemAsync(TOKEN_KEY);
export const getRefreshToken = () => SecureStore.getItemAsync(REFRESH_KEY);

// ── Axios instance ──────────────────────────────────────────────────────────
const api: AxiosInstance = axios.create({
  baseURL: API_BASE,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
});

// Request interceptor: inject Bearer token
api.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
  const token = await getAccessToken();
  if (token && config.headers) {
    config.headers['Authorization'] = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor: auto-refresh on 401
let isRefreshing = false;
let failedQueue: Array<{ resolve: Function; reject: Function }> = [];

const processQueue = (error: any, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) prom.reject(error);
    else prom.resolve(token);
  });
  failedQueue = [];
};

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config;

    if (error.response?.status === 401 && !original._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then((token) => {
            original.headers['Authorization'] = `Bearer ${token}`;
            return api(original);
          })
          .catch((err) => Promise.reject(err));
      }

      original._retry = true;
      isRefreshing = true;

      const refreshToken = await getRefreshToken();
      if (!refreshToken) {
        isRefreshing = false;
        await clearTokens();
        // Let auth store handle redirect
        return Promise.reject(error);
      }

      try {
        const { data } = await axios.post(`${API_BASE}/auth/refresh`, {}, {
          headers: { Authorization: `Bearer ${refreshToken}` },
        });
        const newToken = data.access_token;
        await saveTokens(newToken, refreshToken);
        processQueue(null, newToken);
        original.headers['Authorization'] = `Bearer ${newToken}`;
        return api(original);
      } catch (err) {
        processQueue(err, null);
        await clearTokens();
        return Promise.reject(err);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

export default api;
