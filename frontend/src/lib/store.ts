import { create } from "zustand";
import type { User } from "@/types";

interface AuthState {
  user: User | null;
  token: string | null;
  setAuth: (user: User, token: string) => void;
  logout: () => void;
  hydrateFromStorage: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: null,

  setAuth: (user, token) => {
    localStorage.setItem("access_token", token);
    localStorage.setItem("user", JSON.stringify(user));
    set({ user, token });
  },

  logout: () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("user");
    set({ user: null, token: null });
  },

  hydrateFromStorage: () => {
    const token = localStorage.getItem("access_token");
    const raw = localStorage.getItem("user");
    if (token && raw) {
      try {
        set({ user: JSON.parse(raw), token });
      } catch {
        /* corrupted storage — ignore */
      }
    }
  },
}));
