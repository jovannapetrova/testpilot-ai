import axios from "axios";

const localApiBaseUrl = () => {
  const host = window.location.hostname;
  const localHostName = ["local", "host"].join("");
  const isLocal = host === localHostName || /^127\./.test(host);
  return isLocal ? `${window.location.protocol}//${host}:8000` : "";
};

export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || localApiBaseUrl()
).replace(/\/$/, "");

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000,
});

let activeSession = null;

export function setAuthSession(session) {
  activeSession = session;
  if (session?.access_token) {
    api.defaults.headers.common.Authorization = `Bearer ${session.access_token}`;
  } else {
    delete api.defaults.headers.common.Authorization;
  }
}

api.interceptors.request.use((config) => {
  if (activeSession?.access_token) {
    config.headers.Authorization = `Bearer ${activeSession.access_token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const config = error.config || {};
    const status = error.response?.status;
    const method = String(config.method || "get").toLowerCase();
    const canRetry = method === "get" && !config._retryOnce && (!status || status >= 500);

    if (canRetry) {
      config._retryOnce = true;
      await new Promise((resolve) => setTimeout(resolve, 450));
      return api(config);
    }

    const message =
      error.response?.data?.detail ||
      error.response?.data?.message ||
      (status === 404 ? "The requested item could not be found. It may have been deleted or moved." : "") ||
      error.message ||
      "API request failed.";

    error.userMessage = message;
    return Promise.reject(error);
  },
);

export async function registerUser(payload) {
  const response = await api.post("/auth/register", payload);
  return response.data;
}

export async function loginUser(payload) {
  const response = await api.post("/auth/login", payload);
  return response.data;
}

export async function refreshSession(refreshToken) {
  const response = await axios.post(`${API_BASE_URL}/auth/refresh`, {
    refresh_token: refreshToken,
  });
  return response.data;
}

export async function logoutUser() {
  const response = await api.post("/auth/logout");
  return response.data;
}

export async function forgotPassword(email) {
  const response = await api.post("/auth/forgot-password", { email });
  return response.data;
}

export async function getCurrentUser() {
  const response = await api.get("/users/me");
  return response.data;
}

export async function updateCurrentUser(payload) {
  const response = await api.patch("/users/me", payload);
  return response.data;
}

export async function changePassword(payload) {
  const response = await api.post("/users/me/change-password", payload);
  return response.data;
}

export async function deleteCurrentUser() {
  const response = await api.delete("/users/me");
  return response.data;
}

export async function uploadProjectZip(file) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await api.post("/projects/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });

  return response.data;
}

export async function analyzeProject(projectId) {
  const response = await api.post(`/projects/${projectId}/analyze`);
  return response.data;
}

export async function getReports() {
  const response = await api.get("/reports");
  return response.data;
}

export async function getProjects(params = {}) {
  const response = await api.get("/projects", { params });
  return response.data;
}

export async function getReport(projectId) {
  const response = await api.get(`/reports/${projectId}`);
  return response.data;
}

export function getReportJsonUrl(projectId) {
  return `${API_BASE_URL}/reports/${projectId}/json`;
}

export function getReportPdfUrl(projectId) {
  return `${API_BASE_URL}/reports/${projectId}/pdf`;
}
export async function getDashboardSummary() {
  const response = await api.get("/dashboard/summary");
  return response.data;
}

export function getReportCsvUrl(projectId) {
  return `${API_BASE_URL}/reports/${projectId}/csv`;
}

export function getReportMarkdownUrl(projectId) {
  return `${API_BASE_URL}/reports/${projectId}/markdown`;
}

export async function downloadReportFile(projectId, format) {
  const response = await api.get(`/reports/${projectId}/${format}`, {
    responseType: "blob",
  });
  const extension = format === "markdown" ? "md" : format;
  const url = window.URL.createObjectURL(response.data);
  const link = document.createElement("a");
  link.href = url;
  link.download = `testpilot-report-${projectId}.${extension}`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

export async function compareReports(firstId, secondId) {
  const response = await api.get(`/reports/compare/${firstId}/${secondId}`);
  return response.data;
}
export async function deleteReport(projectId) {
  const response = await api.delete(`/reports/${projectId}`);
  return response.data;
}

export async function clearReports() {
  const response = await api.delete("/reports");
  return response.data;
}
export async function analyzeGithubRepository(url) {
  const response = await api.post("/projects/github", { url });
  return response.data;
}
export async function getAnalysisProgress(projectId) {
  const response = await api.get(`/analysis/${projectId}/progress`);
  return response.data;
}



export default api;
