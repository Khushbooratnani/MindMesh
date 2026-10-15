// Centralized API Base URL for MindMesh Mobile App
// Configure for your server / physical device demo
export const API_BASE_URL: string = 'http://127.0.0.1:8000';

export const getApiUrl = (endpoint: string): string => {
  const base = API_BASE_URL.replace(/\/+$/, '');
  const path = endpoint.replace(/^\/+/, '');
  return `${base}/${path}`;
};
