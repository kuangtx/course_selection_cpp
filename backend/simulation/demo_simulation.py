"""Background actors for the local demo; all writes use normal selection services."""
import copy
import random
import threading
import time
from collections import deque

from ..core.call_planner import call_planner
from ..service.selection import submit_round1, submit_round2


class DemoSimulation:
    MANUAL_STUDENT = "S001"

    def __init__(self, state, *, delay=(0.05, 0.15), rng=None):
        self.state = state
        self.delay = delay
        self.rng = rng or random.Random()
        self._control = threading.RLock()
        self._status_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._clear_status()

    def _clear_status(self):
        with self._status_lock:
            self._status = dict(running=False, stage="idle", active_student=None,
                                round1_processed=0, round1_submitted=0,
                                round2_processed=0, round2_submitted=0,
                                limited_searches=0, events=[], error=None)

    def _update(self, **values):
        with self._status_lock:
            self._status.update(values)

    def _increment(self, key):
        with self._status_lock:
            self._status[key] += 1

    def _log(self, message, student_id=None, kind="info"):
        with self._status_lock:
            self._status["events"].insert(0, dict(time=time.time(), student_id=student_id,
                                                message=message, kind=kind))
            del self._status["events"][50:]

    def status(self):
        with self._status_lock:
            result = copy.deepcopy(self._status)
        with self.state.data["lock"]:
            data = self.state.data
            result.update(phase=data["phase"], state_version=data["state_version"],
                          total_students=len([sid for sid in data["students"] if sid != self.MANUAL_STUDENT]),
                          manual_student=self.MANUAL_STUDENT,
                          pending_alerts=sum(a["student_id"] == self.MANUAL_STUDENT and a["status"] == "PENDING"
                                             for a in data["alerts"].values()))
        return result

    def start(self):
        with self._control:
            if self._thread and self._thread.is_alive():
                return {"ok": True, "simulation": self.status()}
            with self.state.data["lock"]:
                data = self.state.data
                if self.MANUAL_STUDENT not in data["students"]:
                    return dict(ok=False, code="STUDENT_NOT_FOUND", message="演示需要 S001 学生。")
                if data["phase"] not in ("ROUND1_OPEN", "ROUND2_OPEN"):
                    return dict(ok=False, code="WRONG_PHASE", message="当前阶段不能开始自动选课。")
                if data["phase"] == "ROUND1_OPEN" and not data["applications"].get(self.MANUAL_STUDENT):
                    return dict(ok=False, code="DEMO_NEEDS_APPLICATION", message="请先为 S001 提交志愿，再开始模拟，以建立风险提醒基准。")
            self._clear_status()
            self._stop = threading.Event()
            self._update(running=True, stage="round1" if data["phase"] == "ROUND1_OPEN" else "round2")
            self._log("开始自动选课；S001 始终由你手动操作。")
            self._thread = threading.Thread(target=self._run, name="course-demo", daemon=True)
            self._thread.start()
            return {"ok": True, "simulation": self.status()}

    def stop(self):
        with self._control:
            self._stop.set()
            if self._thread:
                self._thread.join()
            if self.status()["stage"] not in ("idle", "finished", "error", "stopped"):
                self._update(running=False, stage="stopped", active_student=None)
                self._log("已停止自动选课，已提交和已录取的课程保留。")
            return {"ok": True, "simulation": self.status()}

    def reset(self):
        # Wait for any in-flight commit before replacing the state's lock/data.
        with self._control:
            self.stop()
            with self.state.data["lock"]:
                self.state.reset()
            self._clear_status()

    def _snapshot(self, student_id):
        with self.state.data["lock"]:
            data = self.state.data
            return dict(phase=data["phase"], student=copy.deepcopy(data["students"][student_id]),
                        courses=copy.deepcopy(data["courses"]), sections=copy.deepcopy(data["sections"]),
                        masks=dict(data["section_masks"]), application=list(data["applications"].get(student_id, [])),
                        enrolled=list(data["enrollments"].get(student_id, [])),
                        revision=data["plan_revision"][student_id],
                        remaining={sid: self.state.get_remaining(sid) for sid in data["sections"]})

    def _choose(self, snapshot, supplement):
        fixed = snapshot["enrolled"] if supplement else []
        allowed = {sid for sid, section in snapshot["sections"].items()
                   if (snapshot["remaining"][sid] if supplement else section["capacity"]) > 0}
        result = call_planner(snapshot["student"], snapshot["courses"], snapshot["sections"],
                              snapshot["masks"], self.state.config, fixed=fixed, allowed=allowed,
                              excluded=set(), allow_partial=supplement)
        if result["search_status"] == "LIMIT_REACHED":
            self._increment("limited_searches")
        plans = [p for p in result["plans"] if supplement or p["is_complete"]]
        if not plans:
            return None
        # Meet requirements first, then maximize the displayed preference score.
        return min(plans, key=lambda p: (not p["is_complete"],
                   len(p["unmet_requirements"]["required_course_ids"]),
                   p["unmet_requirements"]["optional"]["gap"],
                   -p["preference_score"]["total"], tuple(sorted(p["section_ids"]))))

    def _step(self, student_id, phase):
        assert student_id != self.MANUAL_STUDENT
        snapshot = self._snapshot(student_id)
        if snapshot["phase"] != phase:
            return "phase_changed"
        supplement = phase == "ROUND2_OPEN"
        if not supplement and snapshot["application"]:
            self._log("已有志愿，保留原提交。", student_id)
            return "done"
        self._update(active_student=student_id)
        plan = self._choose(snapshot, supplement)
        if self._stop.is_set():
            return "stopped"
        if not plan:
            self._log("当前搜索未找到可提交方案，暂时跳过。", student_id, "warning")
            return "done"
        if supplement:
            additions = [sid for sid in plan["section_ids"] if sid not in snapshot["enrolled"]]
            if not additions:
                self._log("已满足要求。" if plan["is_complete"] else "当前可用课程无法补齐剩余要求。", student_id)
                return "done"
            # One class per turn: later turns re-plan from current seats and pinned enrollments.
            required = set(snapshot["student"]["required_course_ids"])
            additions.sort(key=lambda sid: (snapshot["sections"][sid]["course_id"] not in required, sid))
            result = submit_round2(self.state, student_id, additions[0])
        else:
            result = submit_round1(self.state, student_id, plan["section_ids"], snapshot["revision"])
        if not result["ok"]:
            code = result["code"]
            if code == "WRONG_PHASE":
                return "phase_changed"
            self._log(f"提交未成功：{code}；将按最新状态处理。", student_id, "warning")
            return "retry" if code in ("NO_SEAT", "TIME_CONFLICT", "DUPLICATE_COURSE", "STALE_PLAN") else "done"
        if supplement:
            if result.get("already_enrolled"):
                return "again"
            self._increment("round2_submitted")
            section = snapshot["sections"][additions[0]]
            self._log(f"补选成功：{snapshot['courses'][section['course_id']]['name']}（{additions[0]}）。", student_id, "success")
            return "again"
        self._increment("round1_submitted")
        self._log(f"已提交 {len(plan['section_ids'])} 门课程，偏好分 {plan['preference_score']['total']:.1f}。", student_id, "success")
        return "done"

    def _run(self):
        phase_seen = None
        queue = deque()
        retries = {}
        try:
            while not self._stop.is_set():
                with self.state.data["lock"]:
                    phase = self.state.data["phase"]
                    students = [sid for sid in self.state.data["students"] if sid != self.MANUAL_STUDENT]
                if phase == "CLOSED":
                    self._update(stage="finished")
                    break
                if phase == "DRAWING":
                    self._stop.wait(0.1)
                    continue
                if phase != phase_seen:
                    self.rng.shuffle(students)
                    queue = deque(students)
                    retries.clear()
                    phase_seen = phase
                    self._update(stage="round1" if phase == "ROUND1_OPEN" else "round2")
                    self._log("第一轮：按偏好分选取方案并提交。" if phase == "ROUND1_OPEN"
                              else "第二轮：保留已录取课程，按最新余量逐班补选。")
                if not queue:
                    self._update(active_student=None)
                    if phase == "ROUND1_OPEN":
                        if self.status()["stage"] != "waiting_draw":
                            self._update(stage="waiting_draw")
                            self._log("其他同学已处理完毕，等待你点击“结束第一轮并抽签”。")
                        self._stop.wait(0.5)
                        continue
                    self._update(stage="finished")
                    self._log("本轮自动补选已结束；未补齐的同学可稍后重新尝试。")
                    break
                if self._stop.wait(self.rng.uniform(*self.delay)):
                    break
                student_id = queue.popleft()
                outcome = self._step(student_id, phase)
                if outcome == "stopped":
                    break
                if outcome == "phase_changed":
                    continue
                if outcome == "again":
                    retries.pop(student_id, None)
                    queue.append(student_id)
                elif outcome == "retry" and retries.get(student_id, 0) < 3:
                    retries[student_id] = retries.get(student_id, 0) + 1
                    queue.append(student_id)
                else:
                    self._increment("round1_processed" if phase == "ROUND1_OPEN" else "round2_processed")
        except Exception as error:
            self._update(stage="error", error=str(error))
            self._log("自动选课已停止，请检查服务状态后重新开始。", kind="error")
        finally:
            self._update(running=False, active_student=None)
