export type Phase = 'ROUND1_OPEN' | 'DRAWING' | 'ROUND2_OPEN' | 'CLOSED';
export type Purpose = 'initial' | 'adjustment' | 'supplement';
export interface Preferences {
  course_scores: Record<string, number>;
  early_penalty_per_week: number;
}
export interface Student {
  id: string;
  major_id: string;
  required_course_ids: string[];
  optional_course_ids: string[];
  optional_requirement: { mode: 'count' | 'credits'; target: number };
  preferences: Preferences;
}
export interface Course {
  id: string;
  name: string;
  credits: number;
}
export interface Meeting {
  weeks: number[];
  day: number;
  start: number;
  length: number;
}
export interface Section {
  id: string;
  course_id: string;
  capacity: number;
  meetings: Meeting[];
}
export interface Catalog {
  term: { total_weeks: number; days_per_week: number; periods_per_day: number };
  students: Record<string, Student>;
  courses: Record<string, Course>;
  sections: Record<string, Section>;
}
export interface StudentState {
  phase: Phase;
  current_application: string[];
  enrolled_section_ids: string[];
  applicant_counts: Record<string, number>;
  remaining: Record<string, number>;
  state_version: number;
  plan_revision: number;
}
export interface Alert {
  id: string;
  student_id: string;
  section_id: string;
  plan_revision: number;
  baseline_prob: number;
  current_prob: number;
  status: 'PENDING' | 'HANDLED' | 'EXPIRED';
  created_at: number;
}
export interface Plan {
  section_ids: string[];
  preference_score: {
    total: number;
    details: { course_preference: number; average_early_days_per_week: number; time_score: number };
  };
  is_complete: boolean;
  unmet_requirements: {
    required_course_ids: string[];
    optional: { mode: 'count' | 'credits'; target: number; achieved: number; gap: number };
  };
  risk: {
    section_probabilities: Record<string, number>;
    first_round_all_win_probability: number;
    first_round_failure_risk: number;
  } | null;
  fallback: {
    total: number;
    covered: number;
    uncovered: number;
    unknown: number;
    coverage_lower_bound: number;
    examples: { won_section_ids: string[]; lost_section_ids: string[]; added_section_ids: string[] }[];
  } | null;
  recommendation_score: number | null;
  comparison: {
    changed_course_count: number;
    preference_delta: number;
    risk_improvement: number;
    fallback_coverage_delta: number;
    switched_sections: { course_id: string; old_section_id: string; new_section_id: string }[];
    removed_course_ids: string[];
    added_course_ids: string[];
  } | null;
  new_section_ids: string[] | null;
  explanations: string[];
}
export interface Recommendation {
  state_version: number;
  plan_revision: number;
  purpose: Purpose;
  search_status: 'FOUND' | 'INFEASIBLE' | 'LIMIT_REACHED';
  searched_nodes: number;
  decision: 'SHOW_PLANS' | 'NO_PLAN' | 'KEEP_CURRENT';
  current_plan: Plan | null;
  plans: Plan[];
  limitations: string[];
}
export interface MutationResult {
  ok: true;
  student_state?: StudentState;
}

export interface SimulationStatus {
  running: boolean;
  stage: 'idle' | 'round1' | 'waiting_draw' | 'round2' | 'finished' | 'stopped' | 'error';
  phase: Phase;
  state_version: number;
  total_students: number;
  manual_student: string;
  active_student: string | null;
  round1_processed: number;
  round1_submitted: number;
  round2_processed: number;
  round2_submitted: number;
  limited_searches: number;
  pending_alerts: number;
  error: string | null;
  events: { time: number; student_id: string | null; message: string; kind: string }[];
}
