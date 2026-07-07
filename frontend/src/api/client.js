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

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const message =
      error.response?.data?.detail ||
      error.response?.data?.message ||
      error.message ||
      "API request failed.";

    error.userMessage = message;
    return Promise.reject(error);
  },
);

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
