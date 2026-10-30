"""
tests/test_planner.py
=====================
Kiểm thử tự động cho module pathway planner (M4).
Dùng đồ thị tổng hợp (synthetic graph) để test tính đúng đắn
của lịch học mà không cần dữ liệu thật.
"""

import random
import pytest
from src.syllabus_core.pathway.graph import CourseGraph
from src.syllabus_core.pathway.planner import LearningPathPlanner

# ---------------------------------------------------------------------------
# Dữ liệu đồ thị tổng hợp
# ---------------------------------------------------------------------------

SYNTHETIC_COURSES = {
    "A": {"course_name": "Nhập môn lập trình", "credits": 3, "prerequisites": []},
    "B": {"course_name": "Cấu trúc dữ liệu", "credits": 4, "prerequisites": ["A"]},
    "C": {"course_name": "Giải tích 1",        "credits": 3, "prerequisites": []},
    "D": {"course_name": "Giải tích 2",        "credits": 3, "prerequisites": ["C"]},
    "E": {"course_name": "Cơ sở dữ liệu",     "credits": 3, "prerequisites": ["A"]},
    "F": {"course_name": "Lập trình hướng đối tượng", "credits": 3, "prerequisites": ["A"]},
    "G": {"course_name": "Kiến trúc máy tính", "credits": 3, "prerequisites": []},
    "H": {"course_name": "Hệ điều hành",       "credits": 3, "prerequisites": ["G"]},
    "I": {"course_name": "Mạng máy tính",      "credits": 3, "prerequisites": ["G"]},
    "J": {"course_name": "Trí tuệ nhân tạo",  "credits": 3, "prerequisites": ["B", "D"]},
    "K": {"course_name": "Machine Learning",   "credits": 3, "prerequisites": ["J"]},
    "L": {"course_name": "Đồ án tốt nghiệp",  "credits": 6, "prerequisites": ["K", "E", "F"]},
    # Môn độc lập
    "M": {"course_name": "Kỹ năng mềm",       "credits": 2, "prerequisites": []},
    "N": {"course_name": "Giáo dục thể chất",  "credits": 2, "prerequisites": []},
    "O": {"course_name": "Tiếng Anh 1",        "credits": 3, "prerequisites": []},
    "P": {"course_name": "Tiếng Anh 2",        "credits": 3, "prerequisites": ["O"]},
}

MAX_CREDITS_PER_TERM = 20


@pytest.fixture(scope="module")
def graph():
    """Đồ thị tổng hợp cho toàn bộ test."""
    g = CourseGraph.__new__(CourseGraph)
    g.courses = SYNTHETIC_COURSES
    g._build_graph()
    return g


@pytest.fixture(scope="module")
def planner(graph):
    """Planner với đồ thị tổng hợp."""
    return LearningPathPlanner(graph=graph, max_credits_per_term=MAX_CREDITS_PER_TERM)


# ---------------------------------------------------------------------------
# 1. Kiểm tra cấu trúc đồ thị
# ---------------------------------------------------------------------------

class TestGraphStructure:
    def test_no_cycles(self, graph):
        """Đồ thị không được có chu trình (cycle)."""
        cycles = graph.check_cycles()
        assert cycles == [], f"Phát hiện chu trình: {cycles}"

    def test_all_prerequisites_exist(self, graph):
        """Mọi tiên quyết phải là mã môn có trong đồ thị."""
        for code, info in graph.courses.items():
            for prereq in info.get("prerequisites", []):
                assert prereq in graph.courses, (
                    f"Tiên quyết '{prereq}' của môn '{code}' không tồn tại"
                )

    def test_topo_order_valid(self, graph):
        """Thứ tự topo: tiên quyết phải xuất hiện trước môn phụ thuộc."""
        order = graph.topological_sort()
        pos = {code: i for i, code in enumerate(order)}
        for code, info in graph.courses.items():
            for prereq in info.get("prerequisites", []):
                assert pos[prereq] < pos[code], (
                    f"Thứ tự topo sai: '{prereq}' phải trước '{code}'"
                )

    def test_graph_has_all_courses(self, graph):
        """Đồ thị phải chứa đủ số môn tổng hợp."""
        assert len(graph.courses) == len(SYNTHETIC_COURSES)


# ---------------------------------------------------------------------------
# 2. Kiểm tra chức năng planner
# ---------------------------------------------------------------------------

class TestPlanner:
    def test_credit_limit(self, planner):
        """Mỗi học kỳ không được vượt quá max_credits_per_term."""
        result = planner.plan(target="L", completed=[])
        for term_idx, term in enumerate(result["path"]):
            term_credits = sum(
                SYNTHETIC_COURSES[c]["credits"] for c in term if c in SYNTHETIC_COURSES
            )
            assert term_credits <= MAX_CREDITS_PER_TERM, (
                f"Học kỳ {term_idx + 1} có {term_credits} tín chỉ > giới hạn {MAX_CREDITS_PER_TERM}"
            )

    def test_completed_excluded(self, planner):
        """Môn đã học không được xuất hiện trong kế hoạch."""
        completed = ["A", "C", "G"]
        result = planner.plan(target="J", completed=completed)
        planned_courses = [c for term in result["path"] for c in term]
        for done in completed:
            assert done not in planned_courses, (
                f"Môn đã học '{done}' vẫn xuất hiện trong kế hoạch"
            )

    def test_empty_prerequisites(self, planner):
        """Môn không có tiên quyết (M, N, O) vẫn lên được kế hoạch."""
        for target in ["M", "N", "O"]:
            result = planner.plan(target=target, completed=[])
            planned = [c for term in result["path"] for c in term]
            assert target in planned, f"Môn không tiên quyết '{target}' không có trong kế hoạch"

    def test_target_in_plan(self, planner):
        """Môn đích phải xuất hiện trong kế hoạch."""
        result = planner.plan(target="K", completed=["A", "B", "C", "D", "J"])
        planned = [c for term in result["path"] for c in term]
        assert "K" in planned

    def test_prereq_before_course_in_plan(self, planner):
        """Tiên quyết phải được xếp học trước môn phụ thuộc."""
        result = planner.plan(target="L", completed=[])
        # Flatten: gán index học kỳ cho từng môn
        term_of = {}
        for term_idx, term in enumerate(result["path"]):
            for course in term:
                term_of[course] = term_idx

        for code in term_of:
            if code in SYNTHETIC_COURSES:
                for prereq in SYNTHETIC_COURSES[code].get("prerequisites", []):
                    if prereq in term_of:
                        assert term_of[prereq] < term_of[code], (
                            f"Tiên quyết '{prereq}' (kỳ {term_of[prereq]}) "
                            f"phải trước '{code}' (kỳ {term_of[code]})"
                        )

    def test_plan_target_already_completed(self, planner):
        """Nếu môn đích đã hoàn thành, kế hoạch phải rỗng hoặc có cảnh báo."""
        result = planner.plan(target="A", completed=["A"])
        planned = [c for term in result["path"] for c in term]
        # Môn A đã học → không cần học thêm
        assert "A" not in planned or result.get("warnings")

    def test_no_duplicate_courses_in_plan(self, planner):
        """Mỗi môn chỉ xuất hiện đúng một lần trong kế hoạch."""
        result = planner.plan(target="L", completed=[])
        planned = [c for term in result["path"] for c in term]
        assert len(planned) == len(set(planned)), "Có môn bị trùng trong kế hoạch"

    def test_warnings_field_exists(self, planner):
        """Kết quả phải có trường warnings (có thể rỗng)."""
        result = planner.plan(target="K", completed=[])
        assert "warnings" in result

    def test_total_credits_field(self, planner):
        """Kết quả phải có total_credits."""
        result = planner.plan(target="J", completed=["A"])
        assert "total_credits" in result
        assert result["total_credits"] >= 0


# ---------------------------------------------------------------------------
# 3. 30 random queries stress test
# ---------------------------------------------------------------------------

COURSE_CODES = list(SYNTHETIC_COURSES.keys())

def _random_target_and_completed(seed: int):
    """Sinh ngẫu nhiên (target, completed) hợp lệ từ seed."""
    rng = random.Random(seed)
    target = rng.choice(COURSE_CODES)
    # Chọn ngẫu nhiên tập completed, không bao gồm target
    others = [c for c in COURSE_CODES if c != target]
    k = rng.randint(0, len(others))
    completed = rng.sample(others, k)
    return target, completed


def _validate_plan(result: dict, completed: list) -> list[str]:
    """Kiểm tra kết quả plan và trả về danh sách vi phạm."""
    violations = []
    path = result.get("path", [])
    planned = [c for term in path for c in term]

    # Vi phạm 1: môn đã học vẫn trong kế hoạch
    for done in completed:
        if done in planned:
            violations.append(f"Môn đã học '{done}' vẫn trong kế hoạch")

    # Vi phạm 2: tín chỉ vượt giới hạn
    for term_idx, term in enumerate(path):
        credits = sum(SYNTHETIC_COURSES[c]["credits"] for c in term if c in SYNTHETIC_COURSES)
        if credits > MAX_CREDITS_PER_TERM:
            violations.append(
                f"Kỳ {term_idx + 1}: {credits} tín chỉ > {MAX_CREDITS_PER_TERM}"
            )

    # Vi phạm 3: tiên quyết chưa học lại đứng sau
    term_of = {}
    completed_set = set(completed)
    for term_idx, term in enumerate(path):
        for course in term:
            term_of[course] = term_idx

    for code in term_of:
        if code in SYNTHETIC_COURSES:
            for prereq in SYNTHETIC_COURSES[code].get("prerequisites", []):
                if prereq not in completed_set and prereq not in term_of:
                    violations.append(
                        f"Tiên quyết '{prereq}' của '{code}' không có trong kế hoạch hoặc completed"
                    )
                if prereq in term_of and term_of[prereq] >= term_of[code]:
                    violations.append(
                        f"Tiên quyết '{prereq}' (kỳ {term_of[prereq]}) "
                        f"không trước '{code}' (kỳ {term_of[code]})"
                    )

    # Vi phạm 4: môn trùng
    if len(planned) != len(set(planned)):
        violations.append("Có môn trùng trong kế hoạch")

    return violations


class TestRandomQueries:
    def test_30_random_queries(self, planner):
        """
        Chạy 30 câu hỏi ngẫu nhiên với seed cố định (42–71).
        Mỗi query không được có vi phạm nào.
        """
        all_violations = []
        for seed in range(42, 72):  # 30 seeds: 42..71
            target, completed = _random_target_and_completed(seed)
            result = planner.plan(target=target, completed=completed)
            violations = _validate_plan(result, completed)
            if violations:
                all_violations.append(
                    f"seed={seed}, target={target}, completed={completed}: {violations}"
                )

        assert not all_violations, (
            f"{len(all_violations)} query thất bại:\n" + "\n".join(all_violations)
        )
