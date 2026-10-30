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
from collections import deque
from typing import Optional

from syllabus_core.pathway.graph import CourseNode, PrerequisiteGraph

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
    Sắp xếp topo bằng thuật toán Kahn (1962).

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
    if priority_fn is None:
        def priority_fn(n: CourseNode):
            return (n.recommended_semester, n.avg_bloom_level)

    # Tính in-degree trong subset
    nodes_set = subset if subset is not None else set(graph.nodes.keys())
    in_degree: dict[str, int] = {code: 0 for code in nodes_set}

    for code in nodes_set:
        for neighbor in graph.edges.get(code, set()):
            if neighbor in nodes_set:
                in_degree[neighbor] = in_degree.get(neighbor, 0) + 1

    # Hàng đợi ưu tiên: các môn có in-degree = 0
    ready = sorted(
        [graph.nodes[c] for c in nodes_set if in_degree.get(c, 0) == 0 and c in graph.nodes],
        key=priority_fn,
    )

    result: list[CourseNode] = []
    while ready:
        node = ready.pop(0)
        result.append(node)
        for neighbor_code in sorted(graph.edges.get(node.code, set())):
            if neighbor_code not in nodes_set:
                continue
            in_degree[neighbor_code] -= 1
            if in_degree[neighbor_code] == 0 and neighbor_code in graph.nodes:
                # Chèn đúng vị trí theo priority
                neighbor_node = graph.nodes[neighbor_code]
                inserted = False
                for i, r in enumerate(ready):
                    if priority_fn(r) > priority_fn(neighbor_node):
                        ready.insert(i, neighbor_node)
                        inserted = True
                        break
                if not inserted:
                    ready.append(neighbor_node)

    if len(result) < len(nodes_set):
        logger.warning(
            "Phát hiện chu trình trong đồ thị! %d/%d môn được sắp xếp.",
            len(result), len(nodes_set),
        )
    return result


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
        target_course: str,
        completed_courses: Optional[list[str]] = None,
    ) -> dict:
        """
        Lên kế hoạch học.

        Parameters
        ----------
        target_course : mã môn đích
        completed_courses : danh sách mã môn đã học

        Returns
        -------
        dict với keys: plan, warnings, soft_suggestions
            plan: list of {term: int, courses: list[CourseNode], total_credits: int}
            warnings: list of str (cảnh báo vi phạm)
            soft_suggestions: list of str (gợi ý mềm)
        """
        completed = set(completed_courses or [])
        warnings = []
        soft_suggestions = []

        # Kiểm tra môn đích tồn tại
        if target_course not in self.graph.nodes:
            return {
                "plan": [],
                "warnings": [f"Môn {target_course} không có trong hệ thống."],
                "soft_suggestions": [],
            }

        # Môn cần học
        to_learn = self._get_required_courses(target_course, completed)
        if not to_learn:
            return {
                "plan": [],
                "warnings": [],
                "soft_suggestions": [f"Bạn đã hoàn thành tất cả môn tiên quyết của {target_course}!"],
            }

        # Sắp xếp topo
        sorted_courses = kahn_topological_sort(self.graph, subset=to_learn)

        # Kiểm tra chu trình
        cycles = self.graph.check_cycles()
        if cycles:
            for cycle in cycles:
                warnings.append(f"Chu trình tiên quyết: {' → '.join(cycle)}")

        # Phân bổ học kỳ
        terms: list[dict] = []
        current_term: list[CourseNode] = []
        current_credits = 0

        for course in sorted_courses:
            # Kiểm tra prereqs hoàn thành
            prereqs = self.graph._reverse.get(course.code, set())
            missing_prereqs = prereqs - completed - {c.code for c in current_term}
            placed_codes = {c.code for term in terms for c in term.get("_courses", [])}
            unmet = prereqs - completed - placed_codes
            if unmet:
                warnings.append(
                    f"Môn {course.name} ({course.code}) cần tiên quyết chưa được sắp xếp: "
                    + ", ".join(unmet)
                )

            if current_credits + course.credits > self.max_credits_per_term and current_term:
                # Đóng học kỳ hiện tại
                terms.append({
                    "term": len(terms) + 1,
                    "courses": [{"code": c.code, "name": c.name, "credits": c.credits} for c in current_term],
                    "total_credits": current_credits,
                    "_courses": current_term.copy(),
                })
                current_term = []
                current_credits = 0

            current_term.append(course)
            current_credits += course.credits

        if current_term:
            terms.append({
                "term": len(terms) + 1,
                "courses": [{"code": c.code, "name": c.name, "credits": c.credits} for c in current_term],
                "total_credits": current_credits,
                "_courses": current_term.copy(),
            })

        # Xoá key nội bộ
        for term in terms:
            term.pop("_courses", None)

        # Gợi ý mềm: môn không có tiên quyết cứng nhưng nội dung tương đồng
        soft_suggestions = self._soft_suggestions(target_course, completed, to_learn)

        logger.info(
            "Lộ trình %s: %d môn, %d học kỳ, %d cảnh báo",
            target_course, len(to_learn), len(terms), len(warnings),
        )
        return {
            "plan": terms,
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
