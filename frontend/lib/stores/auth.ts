"use client";
import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { User } from "@/lib/types";

interface AuthState {
  user:  User | null;
  token: string | null;
  setAuth:   (user: User, token: string, expiresIn: number) => void;
  clearAuth: () => void;
  isAuthenticated: () => boolean;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user:  null,
      token: null,

      setAuth(user, token, expiresIn) {
        set({ user, token });
        if (typeof window !== "undefined") {
          localStorage.setItem("hexa_token", token);
          document.cookie = `portal_token=1; path=/; max-age=${expiresIn}; samesite=lax`;
        }
      },

      clearAuth() {
        set({ user: null, token: null });
        if (typeof window !== "undefined") {
          localStorage.removeItem("hexa_token");
          document.cookie = "portal_token=; path=/; max-age=0";
        }
      },

      isAuthenticated: () => !!get().token,
    }),
    {
      name: "hexa-auth",
      partialize: (state) => ({ user: state.user, token: state.token }),
    }
  )
);
