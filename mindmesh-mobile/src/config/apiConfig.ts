// Centralized API Base URL and Dynamic Addressing for MindMesh Mobile App
// Resilient to dynamic IP changes on Debian server

export const DEFAULT_SERVER_HOST = '10.9.11.238';
export const DEFAULT_SERVER_PORT = '8002';

// Dynamic Resolution Priority:
// 1. Runtime override via setCustomApiBaseUrl()
// 2. EXPO_PUBLIC_API_URL environment variable
// 3. Fallback to default server address
let customBaseUrl: string | null = null;

export const setCustomApiBaseUrl = (url: string | null): void => {
  customBaseUrl = url;
};

export const getApiBaseUrl = (): string => {
  if (customBaseUrl) {
    return customBaseUrl.replace(/\/+$/, '');
  }
  if (typeof process !== 'undefined' && process.env && process.env.EXPO_PUBLIC_API_URL) {
    return process.env.EXPO_PUBLIC_API_URL.replace(/\/+$/, '');
  }
  return `http://${DEFAULT_SERVER_HOST}:${DEFAULT_SERVER_PORT}`;
};

// Exported for backward compatibility with static imports
export const API_BASE_URL: string = `http://${DEFAULT_SERVER_HOST}:${DEFAULT_SERVER_PORT}`;

export const getApiUrl = (endpoint: string): string => {
  const base = getApiBaseUrl();
  const path = endpoint.replace(/^\/+/, '');
  return `${base}/${path}`;
};

// Package B Local-First Private Locker Feature Flag (disabled by default)
export const USE_LOCAL_FIRST_LOCKER: boolean = false;
