import time
from ..core.risk import calculate_all_win_probability, should_alert

def save_probability_baselines(state, student_id, section_ids=None):
    data = state.data
    if section_ids is None:
        section_ids = data["applications"].get(student_id, [])

    risk = calculate_all_win_probability(
        student_id,
        list(section_ids),
        sections=data["sections"],
        applicants=data["applicants"],
    )
    probabilities = dict(risk["section_probabilities"])
    data["probability_baselines"][student_id] = probabilities
    return dict(probabilities)

def create_or_update_alerts(state, affected_section_ids):
    data = state.data
    now = time.time()
    affected_section_ids = set(affected_section_ids)
    changed_alerts = []

    _expire_stale_alerts(data, now)

    affected_students = set()
    for section_id in affected_section_ids:
        affected_students.update(data["applicants"][section_id])

    alert_config = state.config.get("alert", {})
    threshold = alert_config.get("threshold", 0.15)
    cooldown_seconds = alert_config.get("cooldown_seconds", 300)

    for student_id in sorted(affected_students):
        baseline = data["probability_baselines"].get(student_id, {})
        section_ids = [
            section_id
            for section_id in sorted(affected_section_ids)
            if section_id in baseline
        ]
        if not section_ids:
            continue

        current_application = data["applications"].get(student_id, [])
        risk = calculate_all_win_probability(
            student_id,
            current_application,
            sections=data["sections"],
            applicants=data["applicants"],
        )
        current_probabilities = risk["section_probabilities"]

        baseline_subset = {
            section_id: baseline[section_id]
            for section_id in section_ids
        }
        current_subset = {
            section_id: current_probabilities[section_id]
            for section_id in section_ids
        }
        alert_result = should_alert(
            baseline_subset,
            current_subset,
            threshold=threshold,
        )

        for section_id in section_ids:
            details = alert_result["details"][section_id]
            existing = _find_pending_alert(data, student_id, section_id)

            if details["triggered"]:
                if existing is not None:
                    existing["current_prob"] = details["current"]
                    existing["updated_at"] = now
                    changed_alerts.append(dict(existing))
                    continue

                cooldown_ends_at = data["alert_cooldowns"].get(student_id, 0)
                if now < cooldown_ends_at:
                    continue

                alert = {
                    "id": f"A{len(data['alerts']) + 1:06d}",
                    "student_id": student_id,
                    "section_id": section_id,
                    "plan_revision": data["plan_revision"][student_id],
                    "baseline_prob": details["baseline"],
                    "current_prob": details["current"],
                    "status": "PENDING",
                    "created_at": now,
                    "updated_at": now,
                    "handled_at": None,
                }
                data["alerts"][alert["id"]] = alert
                changed_alerts.append(dict(alert))
            elif existing is not None:
                existing["current_prob"] = details["current"]
                existing["status"] = "EXPIRED"
                existing["updated_at"] = now
                changed_alerts.append(dict(existing))

    return changed_alerts

def process_alert(state, alert_id, action):
    data = state.data

    with data["lock"]:
        alert = data["alerts"].get(alert_id)
        if alert is None:
            return {
                "ok": False,
                "code": "ALERT_NOT_FOUND",
                "message": f"Alert {alert_id} does not exist.",
            }

        if action != "ack":
            return {
                "ok": False,
                "code": "INVALID_ACTION",
                "message": f"Unsupported alert action: {action}.",
            }

        if data["phase"] != "ROUND1_OPEN":
            return {
                "ok": False,
                "code": "WRONG_PHASE",
                "message": "Alerts can only be handled during round one.",
            }

        if alert["status"] != "PENDING":
            return {
                "ok": False,
                "code": "ALERT_NOT_ACTIVE",
                "message": "This alert has already been handled or expired.",
            }

        student_id = alert["student_id"]
        current_revision = data["plan_revision"][student_id]
        current_application = data["applications"].get(student_id, [])
        if (
            alert["plan_revision"] != current_revision
            or alert["section_id"] not in current_application
        ):
            alert["status"] = "EXPIRED"
            alert["updated_at"] = time.time()
            return {
                "ok": False,
                "code": "ALERT_EXPIRED",
                "message": "The alert is no longer valid for the current application.",
            }

        probabilities = save_probability_baselines(state, student_id)
        now = time.time()
        alert["baseline_prob"] = probabilities[alert["section_id"]]
        alert["current_prob"] = probabilities[alert["section_id"]]
        alert["status"] = "HANDLED"
        alert["updated_at"] = now
        alert["handled_at"] = now

        cooldown_seconds = state.config.get("alert", {}).get("cooldown_seconds", 300)
        data["alert_cooldowns"][student_id] = now + cooldown_seconds
        data["state_version"] += 1

        return {
            "ok": True,
            "state_version": data["state_version"],
            "alert": dict(alert),
            "cooldown_ends_at": data["alert_cooldowns"][student_id],
        }

def get_student_alerts(state, student_id, include_history=False):
    alerts = [
        dict(alert)
        for alert in state.data["alerts"].values()
        if alert["student_id"] == student_id
        and (include_history or alert["status"] == "PENDING")
    ]
    alerts.sort(key=lambda alert: (alert["created_at"], alert["id"]))
    return alerts

def _find_pending_alert(data, student_id, section_id):
    for alert in data["alerts"].values():
        if (
            alert["student_id"] == student_id
            and alert["section_id"] == section_id
            and alert["status"] == "PENDING"
        ):
            return alert
    return None

def _expire_stale_alerts(data, now):
    for alert in data["alerts"].values():
        if alert["status"] != "PENDING":
            continue

        student_id = alert["student_id"]
        if (
            data["phase"] != "ROUND1_OPEN"
            or alert["plan_revision"] != data["plan_revision"][student_id]
            or alert["section_id"] not in data["applications"].get(student_id, [])
        ):
            alert["status"] = "EXPIRED"
            alert["updated_at"] = now
