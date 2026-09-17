import { Select } from "antd";

/** Bộ lọc Năm học / Học kỳ / Khoa – một hàng phía trên nội dung mà nó áp dụng. */
export default function TermFilterBar({ filters, term, onTermChange, facultyId, onFacultyChange, showFaculty = true }) {
  const years = filters?.academic_years ?? [];
  return (
    <>
      <Select
        aria-label="Năm học"
        style={{ width: 180 }}
        value={term?.academic_year}
        onChange={(academic_year) => onTermChange({ ...term, academic_year })}
        options={years.map((y) => ({ value: y, label: `Năm học ${y}` }))}
      />
      <Select
        aria-label="Học kỳ"
        style={{ width: 120 }}
        value={term?.semester}
        onChange={(semester) => onTermChange({ ...term, semester })}
        options={[1, 2, 3].map((s) => ({ value: s, label: s === 3 ? "HK hè" : `HK${s}` }))}
      />
      {showFaculty && (
        <Select
          aria-label="Khoa"
          style={{ width: 240 }}
          value={facultyId ?? "ALL"}
          onChange={(v) => onFacultyChange(v === "ALL" ? undefined : v)}
          options={[{ value: "ALL", label: "Tất cả khoa" },
            ...(filters?.faculties ?? []).map((f) => ({ value: f.id, label: f.name }))]}
        />
      )}
    </>
  );
}
