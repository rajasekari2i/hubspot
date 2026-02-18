// ──────────────────────────────────────────────────────────────
// OIDC session management
// - Token stored in localStorage
// - JWT decoding for user info
// - Auto-redirect on expiry
// ──────────────────────────────────────────────────────────────

import type { JwtUser, UserRole } from '@/types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
const AUTH_TOKEN_KEY = 'auth_token';

// Buffer in seconds before actual expiry to trigger refresh
const EXPIRY_BUFFER_SECONDS = 300; // 5 minutes

// ── Token Storage ────────────────────────────────────────────

export function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(AUTH_TOKEN_KEY);
}

export function setToken(token: string): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(AUTH_TOKEN_KEY, token);
}

export function clearToken(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(AUTH_TOKEN_KEY);
}

// ── JWT Decoding ─────────────────────────────────────────────

function decodeBase64Url(str: string): string {
  // Replace URL-safe characters and pad
  const base64 = str.replace(/-/g, '+').replace(/_/g, '/');
  const padded = base64 + '='.repeat((4 - (base64.length % 4)) % 4);
  return atob(padded);
}

function parseJwt(token: string): JwtUser | null {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const payload = decodeBase64Url(parts[1]);
    return JSON.parse(payload) as JwtUser;
  } catch {
    return null;
  }
}

// ── Authentication State ─────────────────────────────────────

export function isAuthenticated(): boolean {
  const token = getToken();
  if (!token) return false;

  const user = parseJwt(token);
  if (!user) return false;

  // Check token expiry
  const now = Math.floor(Date.now() / 1000);
  return user.exp > now;
}

export function getUser(): JwtUser | null {
  const token = getToken();
  if (!token) return null;

  const user = parseJwt(token);
  if (!user) return null;

  // Return null if expired
  const now = Math.floor(Date.now() / 1000);
  if (user.exp <= now) return null;

  return user;
}

export function getUserRole(): UserRole | null {
  const user = getUser();
  return user?.role ?? null;
}

export function isTokenExpiringSoon(): boolean {
  const user = getUser();
  if (!user) return true;

  const now = Math.floor(Date.now() / 1000);
  return user.exp - now < EXPIRY_BUFFER_SECONDS;
}

// ── Login / Logout ───────────────────────────────────────────

/**
 * Redirect the browser to the backend OIDC login endpoint.
 * The backend will redirect to Google OIDC, which will redirect back
 * to /auth/callback with the authorization code.
 */
export function login(): void {
  if (typeof window === 'undefined') return;

  // Encode the dashboard callback URL so the backend knows where to
  // redirect after exchanging the code.
  const callbackUrl = `${window.location.origin}/auth/callback`;
  const loginUrl = `${API_BASE}/auth/login?redirect_uri=${encodeURIComponent(callbackUrl)}`;
  window.location.href = loginUrl;
}

/**
 * Exchange the OIDC authorization code for a JWT token.
 * Called from the /auth/callback page after the Google OIDC redirect.
 */
export async function handleCallback(code: string): Promise<void> {
  const response = await fetch(`${API_BASE}/auth/callback?code=${encodeURIComponent(code)}`, {
    method: 'GET',
    headers: { 'Accept': 'application/json' },
  });

  if (!response.ok) {
    clearToken();
    throw new Error('Authentication failed. Please try again.');
  }

  const data = await response.json();
  const token = data.access_token || data.token;

  if (!token) {
    throw new Error('No token received from authentication server.');
  }

  setToken(token);
}

/**
 * Clear the local session and redirect to login.
 */
export function logout(): void {
  clearToken();
  if (typeof window !== 'undefined') {
    window.location.href = '/login';
  }
}

// ── Token Refresh ────────────────────────────────────────────

/**
 * Attempt to refresh the JWT if it is expiring soon.
 * The backend /auth/refresh endpoint issues a new token using
 * the existing (still-valid) token.
 */
export async function refreshTokenIfNeeded(): Promise<void> {
  if (!isTokenExpiringSoon()) return;

  const currentToken = getToken();
  if (!currentToken) return;

  try {
    const response = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${currentToken}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      // Token refresh failed -- clear session and redirect
      logout();
      return;
    }

    const data = await response.json();
    const newToken = data.access_token || data.token;
    if (newToken) {
      setToken(newToken);
    }
  } catch {
    // Network error during refresh -- will retry on next interval
    console.warn('Token refresh failed. Will retry.');
  }
}

// ── Periodic Refresh Setup ───────────────────────────────────

let refreshInterval: ReturnType<typeof setInterval> | null = null;

/**
 * Start a background interval that refreshes the token before expiry.
 * Call this once when the dashboard mounts.
 */
export function startTokenRefresh(): void {
  stopTokenRefresh();
  // Check every 60 seconds
  refreshInterval = setInterval(() => {
    refreshTokenIfNeeded();
  }, 60_000);
}

/**
 * Stop the background token refresh interval.
 */
export function stopTokenRefresh(): void {
  if (refreshInterval !== null) {
    clearInterval(refreshInterval);
    refreshInterval = null;
  }
}
