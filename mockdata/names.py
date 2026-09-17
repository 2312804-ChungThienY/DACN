"""Sinh họ tên tiếng Việt có tính tái lập (Faker vi_VN không có tên đệm nên dùng danh sách riêng)."""
from __future__ import annotations

import numpy as np

FAMILY_NAMES = ["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Huỳnh", "Phan", "Vũ",
                "Võ", "Đặng", "Bùi", "Đỗ", "Hồ", "Ngô", "Dương", "Lý"]
FAMILY_WEIGHTS = np.array([31, 11, 9.5, 7, 5, 5, 4.5, 4, 4, 3, 3, 3, 2.5, 2.5, 2, 1.5])

MIDDLE_MALE = ["Văn", "Hữu", "Đức", "Minh", "Quốc", "Thanh", "Công", "Gia", "Hoàng", "Anh", "Tuấn", "Trọng"]
MIDDLE_FEMALE = ["Thị", "Ngọc", "Thu", "Thanh", "Minh", "Bảo", "Khánh", "Mai", "Phương", "Diệu", "Hoài", "Kim"]
GIVEN_MALE = ["An", "Bình", "Cường", "Dũng", "Duy", "Đạt", "Hải", "Hiếu", "Hoàng", "Huy", "Khang", "Khoa",
              "Kiên", "Long", "Lực", "Minh", "Nam", "Nghĩa", "Phong", "Phúc", "Quân", "Sơn", "Tài", "Thành",
              "Thịnh", "Tiến", "Trung", "Tú", "Tuấn", "Việt", "Vinh", "Vũ"]
GIVEN_FEMALE = ["Anh", "Châu", "Chi", "Dung", "Giang", "Hà", "Hạnh", "Hằng", "Hoa", "Hương", "Lan", "Linh",
                "Loan", "Mai", "My", "Ngân", "Ngọc", "Nhi", "Nhung", "Oanh", "Phương", "Quyên", "Tâm", "Thảo",
                "Thư", "Trang", "Trâm", "Uyên", "Vân", "Vy", "Xuân", "Yến"]


def vietnamese_names(rng: np.random.Generator, count: int) -> list[tuple[str, str]]:
    """Trả về [(lastname = họ + đệm, firstname = tên)] theo quy ước mdl_user của Moodle."""
    family_p = FAMILY_WEIGHTS / FAMILY_WEIGHTS.sum()
    families = rng.choice(FAMILY_NAMES, size=count, p=family_p)
    is_male = rng.random(count) < 0.55   # tỷ lệ nam ngành CNTT cao hơn
    names = []
    for family, male in zip(families, is_male):
        middle = rng.choice(MIDDLE_MALE if male else MIDDLE_FEMALE)
        given = rng.choice(GIVEN_MALE if male else GIVEN_FEMALE)
        names.append((f"{family} {middle}", str(given)))
    return names
