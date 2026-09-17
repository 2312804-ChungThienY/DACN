/**
 * Kết nối REST API (SPEC 5.1). Token JWT lưu trong localStorage; 401 ở bất kỳ request nào (trừ đăng nhập)
 * -> đăng xuất và quay về trang đăng nhập.
 */
import axios from "axios";
import { filenameFromDisposition } from "../utils/format.js";

const SESSION_KEY = "lms.analytics.session";

export function loadSession() {
  try {
    const session = JSON.parse(localStorage.getItem(SESSION_KEY));
    return session && session.expiresAt > Date.now() ? session : null;
  } catch {
    return null;
  }
}

export function saveSession(session) {
  localStorage.setItem(SESSION_KEY, JSON.stringify(session));
}

export function clearSession() {
  localStorage.removeItem(SESSION_KEY);
}

export const api = axios.create({
  baseURL: "/api/v1",
  timeout: 60_000,
  // FastAPI nhận mảng dạng lặp tham số: ?risk_level=RED&risk_level=YELLOW (không có [])
  paramsSerializer: { indexes: null },
});

api.interceptors.request.use((config) => {
  const session = loadSession();
  if (session?.token) config.headers.Authorization = `Bearer ${session.token}`;
  return config;
});

let unauthorizedHandler = () => {};
export function setUnauthorizedHandler(handler) {
  unauthorizedHandler = handler;
}

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && !error.config?.url?.endsWith("/auth/login")) unauthorizedHandler();
    return Promise.reject(error);
  },
);

/** Bỏ các tham số rỗng để URL gọn và không gửi chuỗi "undefined". */
export function cleanParams(params = {}) {
  return Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "" && !(Array.isArray(v) && !v.length)),
  );
}

export const get = (url, params) => api.get(url, { params: cleanParams(params) }).then((r) => r.data);
export const post = (url, body) => api.post(url, body).then((r) => r.data);

export async function errorMessage(error) {
  const data = error?.response?.data;
  if (data instanceof Blob) {
    try {
      return (await errorMessage({ response: { data: JSON.parse(await data.text()) } })) ?? "Không tải được file";
    } catch {
      return "Không tải được file";
    }
  }
  const detail = data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => d.msg).join("; ");
  if (error?.code === "ECONNABORTED") return "Máy chủ phản hồi quá lâu, vui lòng thử lại";
  if (!error?.response) return "Không kết nối được máy chủ API";
  return error?.message ?? "Lỗi không xác định";
}

export function errorText(error) {
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (!error?.response) return "Không kết nối được máy chủ API";
  return error?.message ?? "Lỗi không xác định";
}

/** Tải file (Excel/PDF) qua API có xác thực rồi lưu về máy. */
export async function downloadFile(url, params, fallbackName) {
  const response = await api.get(url, { params: cleanParams(params), responseType: "blob" });
  const name = filenameFromDisposition(response.headers["content-disposition"], fallbackName);
  const href = URL.createObjectURL(response.data);
  const link = document.createElement("a");
  link.href = href;
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(href), 10_000);
  return name;
}
