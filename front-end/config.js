// Backend API configuration.
// Defaults to the origin serving this page; override with window.RAG_API_BASE_URL.
const API_BASE_URL = window.RAG_API_BASE_URL || window.location.origin;

// API Endpoints
const API_ENDPOINTS = {
  login: `${API_BASE_URL}/login`,
  logout: `${API_BASE_URL}/logout`,
  chat: `${API_BASE_URL}/chat`,
  upload: `${API_BASE_URL}/upload`,
  sessions: `${API_BASE_URL}/chat/sessions`,
  personas: `${API_BASE_URL}/personas`,
  collectionInfo: `${API_BASE_URL}/collection-info`,
  users: `${API_BASE_URL}/users`,
  updateUserAdmin: `${API_BASE_URL}/update-user-admin`,
  ingest: `${API_BASE_URL}/ingest`,
  resetCollection: `${API_BASE_URL}/reset-collection`,
};
