"""
planner.py
Lên lộ trình học bằng sắp xếp topo Kahn + phân bổ tín chỉ theo học kỳ (M4).

Dùng:
    from syllabus_core.pathway.planner import LearningPlanner
    planner = LearningPlanner(graph)
    result = planner.plan("841470", completed=["841020"])
"""

from __future__ import annotations

import logging
from typing import Optional

from syllabus_core.pathway.graph import CourseNode, PrerequisiteGraph, kahn_heap_sort

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Kahn topological sort
# ---------------------------------------------------------------------------

def kahn_topological_sort(
    graph: PrerequisiteGraph,
    subset: set[str] | None = None,
    priority_fn=None,
) -> list[CourseNode]:
    """
    Sắp xếp topo bằng thuật toán Kahn + min-heap O((V + E) log V).

    Parameters
    ----------
    graph : PrerequisiteGraph
    subset : chỉ sắp xếp các môn trong subset (None = tất cả)
    priority_fn : callable(CourseNode) → comparable, để chọn môn khi nhiều môn sẵn sàng
                  Mặc định: ưu tiên recommended_semester tăng dần, sau đó avg_bloom_level tăng dần

    Returns
    -------
    list[CourseNode] theo thứ tự topo (tiên quyết trước)
    """
    nodes_set = subset if subset is not None else set(graph.nodes.keys())
    return kahn_heap_sort(graph.nodes, graph.edges, subset=nodes_set, priority_fn=priority_fn)


# ---------------------------------------------------------------------------
# LearningPlanner
# ---------------------------------------------------------------------------

class LearningPlanner:
    """
    Lên lộ trình học cho sinh viên.

    Thuật toán:
        1. Lấy tập tổ tiên của môn đích.
        2. Loại bỏ môn đã học.
        3. Sắp xếp topo Kahn (ưu tiên học kỳ → mức Bloom tăng dần).
        4. Phân bổ vào học kỳ theo giới hạn tín chỉ.
    """

    def __init__(self, graph: PrerequisiteGraph, max_credits_per_term: int = 20):
        self.graph = graph
        self.max_credits_per_term = max_credits_per_term

    def _get_required_courses(
        self,
        target_code: str,
        completed: set[str],
    ) -> set[str]:
        """Tất cả môn cần học: tổ tiên của target + target, trừ completed."""
        ancestors = self.graph.get_ancestors(target_code)
        required = ancestors | {target_code}
        return required - completed

    def plan(
        self,
        target_course: Optional[str] = None,
        completed_courses: Optional[list[str]] = None,
        *,
        target: Optional[str] = None,
        completed: Optional[list[str]] = None,
    ) -> dict:
        """
        Lên kế hoạch học.

        Parameters
        ----------
        target_course / target : mã môn đích
        completed_courses / completed : danh sách mã môn đã học

        Returns
        -------
        dict với keys: plan, path, total_credits, total_courses, target_course, warnings, soft_suggestions
        """
        if target_course is None:
            target_course = target
        if completed_courses is None:
            completed_courses = completed

        if not target_course:
            return {
                "target_course": "",
                "plan": [],
                "path": [],
                "total_credits": 0,
                "total_courses": 0,
                "warnings": ["Thiếu mã môn đích (target_course)."],
                "soft_suggestions": [],
            }

        completed_set = set(completed_courses or [])
        warnings: list[str] = []
        soft_suggestions: list[str] = []

        # Kiểm tra môn đích tồn tại
        if target_course not in self.graph.nodes:
            return {
                "target_course": target_course,
                "plan": [],
                "path": [],
                "total_credits": 0,
                "total_courses": 0,
                "warnings": [f"Môn {target_course} không có trong hệ thống."],
                "soft_suggestions": [],
            }

        # Nếu môn đích đã hoàn thành
        if target_course in completed_set:
            return {
                "target_course": target_course,
                "plan": [],
                "path": [],
                "total_credits": 0,
                "total_courses": 0,
                "warnings": [],
                "soft_suggestions": [f"Bạn đã hoàn thành môn {target_course}!"],
            }

        # Môn cần học (tổ tiên + đích, loại bỏ môn đã học)
        to_learn = self._get_required_courses(target_course, completed_set)
        if not to_learn:
            return {
                "target_course": target_course,
                "plan": [],
                "path": [],
                "total_credits": 0,
                "total_courses": 0,
                "warnings": [],
                "soft_suggestions": [f"Bạn đã hoàn thành tất cả môn tiên quyết của {target_course}!"],
            }

        # Kiểm tra chu trình
        cycles = self.graph.check_cycles()
        if cycles:
            for cycle in cycles:
                warnings.append(f"Chu trình tiên quyết: {' → '.join(cycle)}")

        # Phân bổ học kỳ theo từng đợt (level-by-level Kahn):
        # Đảm bảo mọi tiên quyết phải nằm ở học kỳ TRƯỚC (term_of[prereq] < term_of[course])
        terms: list[dict] = []
        remaining = {c for c in to_learn if c in self.graph.nodes}
        placed_codes = set(completed_set)
        prereqs_in_plan = {
            c: (self.graph._reverse.get(c, set()) & remaining)
            for c in remaining
        }

        while remaining:
            eligible = [
                self.graph.nodes[c]
                for c in remaining
                if prereqs_in_plan[c] <= placed_codes
            ]

            if not eligible:
                # Chỉ xảy ra khi đồ thị có chu trình trong tập remaining
                fallback_code = min(
                    remaining,
                    key=lambda c: (len(prereqs_in_plan[c] - placed_codes), c),
                )
                unmet = prereqs_in_plan[fallback_code] - placed_codes
                node = self.graph.nodes[fallback_code]
                warnings.append(
                    f"Môn {node.name} ({node.code}) cần tiên quyết chưa được sắp xếp: "
                    + ", ".join(sorted(unmet))
                )
                eligible = [node]

            eligible.sort(key=lambda n: (n.recommended_semester, n.avg_bloom_level, n.code))

            current_term: list[CourseNode] = []
            current_credits = 0
            for course in eligible:
                if current_credits + course.credits <= self.max_credits_per_term:
                    current_term.append(course)
                    current_credits += course.credits
                elif not current_term:
                    current_term.append(course)
                    current_credits += course.credits
                    warnings.append(
                        f"Môn {course.code} ({course.credits} TC) vượt giới hạn {self.max_credits_per_term} TC/kỳ."
                    )
                    break

            terms.append({
                "term": len(terms) + 1,
                "courses": [{"code": c.code, "name": c.name, "credits": c.credits} for c in current_term],
                "total_credits": current_credits,
            })
            for c in current_term:
                remaining.discard(c.code)
                placed_codes.add(c.code)

        # Gợi ý mềm: môn không có tiên quyết cứng nhưng nội dung tương đồng
        soft_suggestions = self._soft_suggestions(target_course, completed_set, to_learn)
        path = [[c["code"] for c in t["courses"]] for t in terms]
        total_credits = sum(t["total_credits"] for t in terms)
        total_courses = sum(len(t["courses"]) for t in terms)

        logger.info(
            "Lộ trình %s: %d môn, %d học kỳ, %d cảnh báo",
            target_course, total_courses, len(terms), len(warnings),
        )
        return {
            "target_course": target_course,
            "plan": terms,
            "path": path,
            "total_credits": total_credits,
            "total_courses": total_courses,
            "warnings": warnings,
            "soft_suggestions": soft_suggestions,
        }

    def _soft_suggestions(
        self,
        target: str,
        completed: set[str],
        to_learn: set[str],
    ) -> list[str]:
        """Gợi ý môn nên học trước dù không có tiên quyết cứng."""
        suggestions = []
        target_node = self.graph.nodes.get(target)
        if not target_node:
            return suggestions

        # Môn có Bloom thấp hơn và không trong to_learn → gợi ý
        for code, node in self.graph.nodes.items():
            if code in completed or code in to_learn or code == target:
                continue
            if node.avg_bloom_level < target_node.avg_bloom_level - 1:
                suggestions.append(
                    f"Nên học {node.name} ({code}) trước vì mức Bloom thấp hơn ({node.avg_bloom_level:.1f} < {target_node.avg_bloom_level:.1f})."
                )
            if len(suggestions) >= 3:
                break
        return suggestions

    def validate_plan(
        self,
        plan: list[dict],
        completed: set[str],
    ) -> tuple[bool, list[str]]:
        """
        Kiểm tra kế hoạch không vi phạm tiên quyết.

        Returns
        -------
        (is_valid, list_of_violations)
        """
        violations = []
        placed_so_far: set[str] = set(completed)

        for term_info in plan:
            term_codes = {c["code"] for c in term_info.get("courses", [])}
            for code in term_codes:
                prereqs = self.graph._reverse.get(code, set())
                unmet = prereqs - placed_so_far
                if unmet:
                    violations.append(
                        f"Kỳ {term_info['term']}: {code} cần tiên quyết chưa hoàn thành: {unmet}"
                    )
            placed_so_far |= term_codes

        return len(violations) == 0, violations


# Alias tương thích với tests/test_planner.py
LearningPathPlanner = LearningPlanner
