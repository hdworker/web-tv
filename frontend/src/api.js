import axios from "axios";

const API_BASE = "/api";

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    "Content-Type": "application/json",
  },
});

export const scheduleApi = {
  getByDate: (date) => api.get(`/schedule/${date}`),
  getByPeriod: (startDate, endDate) =>
    api.get(`/schedule?start_date=${startDate}&end_date=${endDate}`),
  saveToDb: (startDate, endDate) =>
    api.post(`/schedule/save?start_date=${startDate}&end_date=${endDate}`),
};

export const videosApi = {
  list: (status, limit = 50) =>
    api.get(`/videos?status=${status || ""}&limit=${limit}`),
  get: (id) => api.get(`/videos/${id}`),
  create: (video) => api.post("/videos", video),
  download: (id) => api.post(`/videos/${id}/download`),
  stopDownload: (id) => api.post(`/videos/${id}/download/stop`),
  concat: (id) => api.post(`/videos/${id}/concat`),
  transcribe: (id) => api.post(`/videos/${id}/transcribe`),
  getLogs: (id) => api.get(`/videos/${id}/logs`),
  getDetails: (id) => api.get(`/videos/${id}/details`),
  openFolder: (id) => api.post(`/videos/${id}/open-folder`),
  streamUrl: (id) => `/api/videos/${id}/stream`,
  getSegmentsInfo: (id) => api.get(`/videos/${id}/segments-info`),
  getTranscript: (id) => api.get(`/videos/${id}/transcript`),
};

export default api;
