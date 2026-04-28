"use client";

const TOKEN_KEY  = "hexa_portal_token";
const EXPIRY_KEY = "hexa_portal_expiry";

export function setToken(token: string, expiresIn: number): void {
  localStorage.setItem(TOKEN_KEY,  token);
  localStorage.setItem(EXPIRY_KEY, String(Date.now() + expiresIn * 1000));
  // cookie so middleware can check auth without accessing localStorage
  document.cookie = `portal_token=1; path=/; max-age=${expiresIn}; samesite=lax`;
}

export function getToken(): string | null {
  const expiry = localStorage.getItem(EXPIRY_KEY);
  if (expiry && Date.now() > Number(expiry)) {
    clearToken();
    return null;
  }
  return localStorage.getItem(TOKEN_KEY);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(EXPIRY_KEY);
  document.cookie = "portal_token=; path=/; max-age=0";
}

export function isAuthenticated(): boolean {
  return getToken() !== null;
}
