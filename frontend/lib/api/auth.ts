import { api } from "./client";
import type { TokenResponse, User } from "@/lib/types";

/**
 * Multi-user login via OAuth2 form (email + password).
 * The backend expects application/x-www-form-urlencoded.
 */
export async function loginOAuth2(email: string, password: string): Promise<TokenResponse> {
  const { data } = await api.post<TokenResponse>(
    "/auth/login",
    new URLSearchParams({ username: email, password }),
    { headers: { "Content-Type": "application/x-www-form-urlencoded" } }
  );
  return data;
}

/**
 * Legacy single-password login (no user DB needed).
 * Useful during initial setup before any users are created.
 */
export async function loginWithPassword(password: string): Promise<TokenResponse> {
  const { data } = await api.post<TokenResponse>("/auth/token", { password });
  return data;
}

export async function getMe(): Promise<User> {
  const { data } = await api.get<User>("/auth/me");
  return data;
}

export async function refreshToken(): Promise<TokenResponse> {
  const { data } = await api.post<TokenResponse>("/auth/refresh");
  return data;
}

export async function createUser(body: {
  email: string; password: string; full_name?: string; role?: string;
}): Promise<User> {
  const { data } = await api.post<User>("/auth/users", body);
  return data;
}

export async function listUsers(): Promise<User[]> {
  const { data } = await api.get<User[]>("/auth/users");
  return data;
}
