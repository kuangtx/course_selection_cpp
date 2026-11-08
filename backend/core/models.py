import copy
import threading
import json
from .time_mask import build_mask

class SystemState:
    def __init__(self, data, config):
        validate_data(data)
        # Keep pristine source data so reset can rebuild a fresh state.
        self._source_data = copy.deepcopy(data)
        self.config = copy.deepcopy(config)
        self.data = self._build_data(self._source_data)

    def _build_data(self, source):
        students = copy.deepcopy(source['students'])
        courses = copy.deepcopy(source['courses'])
        sections = copy.deepcopy(source['sections'])
        term = copy.deepcopy(source['term'])

        section_masks = {}
        for section_id, section in sections.items():
            section_masks[section_id] = build_mask(
                section['meetings'],
                total_weeks=term['total_weeks'],
                days_per_week=term['days_per_week'],
                periods_per_day=term['periods_per_day'],
            )

        return {
            'term': term,
            'students': students,
            'courses': courses,
            'sections': sections,
            'section_masks': section_masks,

            'phase': 'ROUND1_OPEN',
            'applications': {},
            'applicants': {
                section_id: set()
                for section_id in sections
            },
            'enrollments': {},
            'enrolled_students': {
                section_id: set()
                for section_id in sections
            },

            'state_version': 0,
            'plan_revision': {
                student_id: 0
                for student_id in students
            },

            'probability_baselines': {},
            'alerts': {},
            'alert_cooldowns': {},

            'lock': threading.Lock(),
        }

    def reset(self):
        # Discard all applications, enrollments, and alerts.
        self.data = self._build_data(self._source_data)

    def get_remaining(self, section_id):
        section = self.data['sections'][section_id]
        enrolled = self.data['enrolled_students'][section_id]
        return section['capacity'] - len(enrolled)

    def get_student_taken_mask(self, student_id):
        taken_mask = 0
        enrolled_section_ids = self.data['enrollments'].get(student_id, [])

        for section_id in enrolled_section_ids:
            taken_mask |= self.data['section_masks'][section_id]

        return taken_mask

    def create_snapshot(self, student_id, purpose):
        if purpose not in ("initial", "adjustment", "supplement"):
            raise ValueError(f"Unsupported recommendation purpose: {purpose}")

        # Snapshots are copies; recommendation code cannot mutate official state.
        snapshot = {
            'phase': self.data['phase'],
            'state_version': self.data['state_version'],
            'plan_revision': self.data['plan_revision'][student_id],
        }

        if purpose in ('initial', 'adjustment'):
            snapshot['applicants'] = {
                section_id: set(applicants)
                for section_id, applicants in self.data['applicants'].items()
            }

        if purpose == 'adjustment':
            snapshot['current_application'] = list(
                self.data['applications'].get(student_id, [])
            )

        if purpose == 'supplement':
            snapshot['enrolled_section_ids'] = list(
                self.data['enrollments'].get(student_id, [])
            )
            snapshot['remaining'] = {
                section_id: self.get_remaining(section_id)
                for section_id in self.data['sections']
            }

        return snapshot

def load_data(path):
    """Load raw catalog data from a JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for field in ("term", "students", "courses", "sections"):
        if field not in data:
            raise ValueError(f"Missing top-level field: {field}")

    return data


def validate_data(data):
    """Validate loaded data and raise ValueError with its location on failure."""
    term = data["term"]
    students = data["students"]
    courses = data["courses"]
    sections = data["sections"]

    for name in ("total_weeks", "days_per_week", "periods_per_day"):
        value = term.get(name)
        if type(value) is not int or value < 1:
            raise ValueError(f"term.{name} must be a positive integer, got {value!r}")

    for course_id, course in courses.items():
        if course.get("id") != course_id:
            raise ValueError(
                f"Course ID mismatch: key {course_id}, content {course.get('id')}"
            )
        credits = course.get("credits")
        if isinstance(credits, bool) or not isinstance(credits, (int, float)) or credits <= 0:
            raise ValueError(f"Course {course_id} credits must be positive, got {credits!r}")

    for section_id, section in sections.items():
        if section.get("id") != section_id:
            raise ValueError(
                f"Section ID mismatch: key {section_id}, content {section.get('id')}"
            )
        if section.get("course_id") not in courses:
            raise ValueError(
                f"Section {section_id} references unknown course {section.get('course_id')}"
            )
        capacity = section.get("capacity")
        if type(capacity) is not int or capacity < 1:
            raise ValueError(
                f"Section {section_id} capacity must be a positive integer, got {capacity!r}"
            )

        # build_mask validates week/day/period ranges and meeting overlaps.
        try:
            build_mask(
                section.get("meetings", []),
                total_weeks=term["total_weeks"],
                days_per_week=term["days_per_week"],
                periods_per_day=term["periods_per_day"],
            )
        except (ValueError, TypeError, KeyError) as e:
            raise ValueError(f"Invalid meetings for section {section_id}: {e}") from e

    for student_id, student in students.items():
        if student.get("id") != student_id:
            raise ValueError(
                f"Student ID mismatch: key {student_id}, content {student.get('id')}"
            )

        required = student.get("required_course_ids", [])
        optional = student.get("optional_course_ids", [])

        for course_id in required + optional:
            if course_id not in courses:
                raise ValueError(
                    f"Student {student_id} references unknown course {course_id}"
                )

        if len(set(required)) != len(required):
            raise ValueError(f"Student {student_id} has duplicate required course IDs")
        if len(set(optional)) != len(optional):
            raise ValueError(f"Student {student_id} has duplicate optional course IDs")

        overlap = set(required) & set(optional)
        if overlap:
            raise ValueError(
                f"Student {student_id} has courses in both required and optional sets: "
                f"{sorted(overlap)}"
            )

        requirement = student.get("optional_requirement", {})
        mode = requirement.get("mode")
        target = requirement.get("target")

        if mode not in ("count", "credits"):
            raise ValueError(
                f"Student {student_id} optional_requirement.mode must be 'count' or 'credits'"
            )
        if mode == "count":
            if type(target) is not int or target < 0:
                raise ValueError(
                    f"Student {student_id} optional count target must be a "
                    f"non-negative integer, got {target!r}"
                )
        else:
            if isinstance(target, bool) or not isinstance(target, (int, float)) or target < 0:
                raise ValueError(
                    f"Student {student_id} optional credit target must be "
                    f"non-negative, got {target!r}"
                )