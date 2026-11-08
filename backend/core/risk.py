"""Lottery probability estimates and cumulative probability-drop alerts."""

from math import isfinite


def _validate_probability(value: float, name: str) -> None:
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not isfinite(value) or not 0 <= value <= 1):
        raise ValueError(f"{name} must be a finite number between zero and one")


def calculate_all_win_probability(
        student_id: str, section_ids: list[str],
        *, sections: dict,
        applicants: dict[str, set[str]]
        ) -> dict:
    if len(section_ids) != len(set(section_ids)):
        raise ValueError("section_ids must not contain duplicates")
    for section_id in section_ids:
        if section_id not in sections or section_id not in applicants:
            raise ValueError(f"Missing section or applicant data: {section_id}")
        capacity = sections[section_id].get("capacity")
        if type(capacity) is not int or capacity < 0:
            raise ValueError("capacity must be a non-negative integer")

    result = {'section_probabilities': {}}

    # Count the candidate once, whether or not they have already applied.
    for section_id in sorted(section_ids):
        probability = min(sections[section_id]['capacity'] / (len(applicants[section_id] - {student_id}) + 1), 1.0)
        result['section_probabilities'][section_id] = probability

    # Separate section lotteries are modeled as independent events.
    first_round_all_win_probability = 1.0

    for probability in result['section_probabilities'].values():
        first_round_all_win_probability *= probability

    result['first_round_all_win_probability'] = first_round_all_win_probability
    result['first_round_failure_risk'] = 1 - first_round_all_win_probability

    return result

def should_alert(
        baseline_probabilities: dict[str, float], current_probabilities: dict[str, float],
         *, threshold: float = 0.15
        ) -> dict:
    _validate_probability(threshold, "threshold")
    if threshold == 0:
        raise ValueError("threshold must be greater than zero")
    if baseline_probabilities.keys() != current_probabilities.keys():
        raise ValueError("Baseline and current section IDs must match")
    for section_id in baseline_probabilities:
        _validate_probability(baseline_probabilities[section_id], "baseline")
        _validate_probability(current_probabilities[section_id], "current")

    result = {'threshold': threshold, 'triggered_section_ids': [], 'details': {}}

    for section_id in sorted(baseline_probabilities.keys()):
        baseline = float(baseline_probabilities[section_id])
        current = float(current_probabilities[section_id])
        drop = baseline - current
        result['details'][section_id] = {
            'baseline': baseline,
             'current': current,
             'drop': drop,
             'triggered': False
            }

        if drop >= threshold:
            result['triggered_section_ids'].append(section_id)
            result['details'][section_id]['triggered'] = True

    result['should_alert'] = bool(result['triggered_section_ids'])

    return result