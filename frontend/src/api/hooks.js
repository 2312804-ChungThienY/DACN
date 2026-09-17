/** React Query hook cho từng endpoint (SPEC 5.1). */
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { get, post } from "./client.js";

const termParams = (term) => (term?.academic_year && term?.semester
  ? { academic_year: term.academic_year, semester: term.semester }
  : {});

// ----------------------------------------------------------------------------- dùng chung
export const useFilters = () => useQuery({
  queryKey: ["filters"], queryFn: () => get("/filters"), staleTime: 5 * 60_000,
});

export const useEtlStatus = () => useQuery({
  queryKey: ["etl-status"], queryFn: () => get("/etl/status"), refetchInterval: 5 * 60_000,
});

// ----------------------------------------------------------------------------- Admin 1.1
export const useKpis = (term, facultyId) => useQuery({
  queryKey: ["kpis", term, facultyId],
  queryFn: () => get("/admin/overview/kpis", { ...termParams(term), faculty_id: facultyId }),
  enabled: !!term, placeholderData: keepPreviousData, refetchInterval: 60_000,
});

export const useEnrollmentByFaculty = (term) => useQuery({
  queryKey: ["by-faculty", term],
  queryFn: () => get("/admin/enrollment/by-faculty", termParams(term)),
  enabled: !!term, placeholderData: keepPreviousData,
});

export const useFacultyCourses = (facultyId, term, sort = "active_rate", order = "desc") => useQuery({
  queryKey: ["faculty-courses", facultyId, term, sort, order],
  queryFn: () => get(`/admin/enrollment/faculties/${facultyId}/courses`, { ...termParams(term), sort, order }),
  enabled: !!facultyId && !!term, placeholderData: keepPreviousData,
});

export const useCourseStudents = (courseId, params) => useQuery({
  queryKey: ["course-students", courseId, params],
  queryFn: () => get(`/admin/enrollment/courses/${courseId}/students`, params),
  enabled: !!courseId, placeholderData: keepPreviousData,
});

// ----------------------------------------------------------------------------- Admin 1.2
export const useTrafficHourly = (from, to) => useQuery({
  queryKey: ["traffic-hourly", from, to],
  queryFn: () => get("/admin/traffic/hourly", { from, to }),
  placeholderData: keepPreviousData,
});

export const useTrafficRealtime = () => useQuery({
  queryKey: ["traffic-realtime"], queryFn: () => get("/admin/traffic/realtime"),
  refetchInterval: 60_000,           // SPEC 5.1: frontend gọi lại mỗi 60 giây
});

export const useTrafficHeatmap = (weeks) => useQuery({
  queryKey: ["traffic-heatmap", weeks], queryFn: () => get("/admin/traffic/heatmap", { weeks }),
  placeholderData: keepPreviousData,
});

// ----------------------------------------------------------------------------- Admin 1.3
export const useReportPreview = (params, enabled) => useQuery({
  queryKey: ["report-preview", params],
  queryFn: () => get("/admin/reports/preview", params),
  enabled, placeholderData: keepPreviousData,
});

// ----------------------------------------------------------------------------- Giảng viên
export const useTeacherCourses = () => useQuery({
  queryKey: ["teacher-courses"], queryFn: () => get("/teacher/courses"),
});

export const useRiskSummary = (courseId) => useQuery({
  queryKey: ["risk-summary", courseId], queryFn: () => get(`/teacher/courses/${courseId}/risk-summary`),
  enabled: !!courseId,
});

export const useRiskStudents = (courseId, params) => useQuery({
  queryKey: ["risk-students", courseId, params],
  queryFn: () => get(`/teacher/courses/${courseId}/students`, params),
  enabled: !!courseId, placeholderData: keepPreviousData,
});

export const useStudentDetail = (courseId, userId) => useQuery({
  queryKey: ["student-detail", courseId, userId],
  queryFn: () => get(`/teacher/courses/${courseId}/students/${userId}`),
  enabled: !!courseId && !!userId,
});

export const useStudentCompare = (courseId, userId) => useQuery({
  queryKey: ["student-compare", courseId, userId],
  queryFn: () => get(`/teacher/courses/${courseId}/students/${userId}/compare`),
  enabled: !!courseId && !!userId,
});

export const useCourseProgress = (courseId, granularity) => useQuery({
  queryKey: ["course-progress", courseId, granularity],
  queryFn: () => get(`/teacher/courses/${courseId}/progress`, { granularity }),
  enabled: !!courseId, placeholderData: keepPreviousData,
});

export function useCreateIntervention(courseId, userId) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body) => post(`/teacher/courses/${courseId}/students/${userId}/interventions`, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["student-detail", courseId, userId] }),
  });
}
