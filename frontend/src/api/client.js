import axios from "axios";

const API_BASE_URL = "http://127.0.0.1:8000";

const api = axios.create({
  baseURL: API_BASE_URL,
});

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
