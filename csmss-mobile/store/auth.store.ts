// store/auth.store.ts — Zustand global auth state
import { create } from 'zustand';
import api, { saveTokens, clearTokens, getAccessToken } from '../services/api';

interface StudentProfile {
  id: number;
  roll_no: string | null;
  prn: string | null;
  batch: string | null;
  class_id: number | null;
  class_name: string | null;
  tg_id: number | null;
}

interface TeacherProfile {
  id: number;
  designation: string | null;
  department_id: number | null;
  department: string | null;
}

interface User {
  id: number;
  name: string;
  email: string;
  role: string;
  phone: string | null;
  profile_pic: string | null;
  must_change_password: boolean;
  status: string;
  student?: StudentProfile;
  teacher?: TeacherProfile;
}

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;

  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  rehydrate: () => Promise<void>;
  updateUser: (user: Partial<User>) => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user:            null,
  isAuthenticated: false,
  isLoading:       true,

  login: async (email: string, password: string) => {
    const { data } = await api.post('/auth/login', { email, password });
    await saveTokens(data.access_token, data.refresh_token);
    set({ user: data.user, isAuthenticated: true });
  },

  logout: async () => {
    try {
      await api.post('/auth/logout');
    } catch (_) {
      // Silent — even if the request fails, clear local tokens
    }
    await clearTokens();
    set({ user: null, isAuthenticated: false });
  },

  rehydrate: async () => {
    try {
      const token = await getAccessToken();
      if (!token) {
        set({ isLoading: false, isAuthenticated: false });
        return;
      }
      const { data } = await api.get('/auth/me');
      set({ user: data.user, isAuthenticated: true, isLoading: false });
    } catch (_) {
      await clearTokens();
      set({ isLoading: false, isAuthenticated: false });
    }
  },

  updateUser: (updates: Partial<User>) => {
    const current = get().user;
    if (current) set({ user: { ...current, ...updates } });
  },
}));

// Helpers
export const useRole = () => useAuthStore((s) => s.user?.role ?? '');
export const useStudent = () => useAuthStore((s) => s.user?.student);
export const useTeacher = () => useAuthStore((s) => s.user?.teacher);
