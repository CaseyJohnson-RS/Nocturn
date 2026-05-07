import { create } from 'zustand';
import type { UserResponse } from '@/types/api';

interface AuthState {
  user: UserResponse | null;
  accessToken: string | null;
  isInitialized: boolean;
  setUser: (user: UserResponse) => void;
  setAccessToken: (token: string) => void;
  setInitialized: () => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  accessToken: null,
  isInitialized: false,

  setUser: (user) => set({ user }),
  setAccessToken: (accessToken) => set({ accessToken }),
  setInitialized: () => set({ isInitialized: true }),

  logout: () =>
    set({ user: null, accessToken: null }),
}));
