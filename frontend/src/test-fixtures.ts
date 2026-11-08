import type { Catalog, Plan, Recommendation, StudentState, SimulationStatus } from './types';

export const catalog: Catalog = {
  term: { total_weeks: 18, days_per_week: 7, periods_per_day: 13 },
  students: {
    S001: {
      id: 'S001',
      major_id: 'SE',
      required_course_ids: ['MATH'],
      optional_course_ids: ['ART'],
      optional_requirement: { mode: 'count', target: 1 },
      preferences: { course_scores: { MATH: 80, ART: 90 }, early_penalty_per_week: 10 },
    },
    S002: {
      id: 'S002',
      major_id: 'AI',
      required_course_ids: ['MATH'],
      optional_course_ids: ['ART'],
      optional_requirement: { mode: 'credits', target: 2 },
      preferences: { course_scores: { MATH: 60, ART: 70 }, early_penalty_per_week: 5 },
    },
  },
  courses: {
    MATH: { id: 'MATH', name: '高等数学', credits: 4 },
    ART: { id: 'ART', name: '艺术鉴赏', credits: 2 },
  },
  sections: {
    MATH_A: {
      id: 'MATH_A',
      course_id: 'MATH',
      capacity: 1,
      meetings: [{ weeks: [1, 3], day: 1, start: 1, length: 2 }],
    },
    MATH_B: {
      id: 'MATH_B',
      course_id: 'MATH',
      capacity: 2,
      meetings: [{ weeks: [2, 4], day: 7, start: 12, length: 2 }],
    },
    ART_A: {
      id: 'ART_A',
      course_id: 'ART',
      capacity: 2,
      meetings: [{ weeks: [1, 2, 3], day: 2, start: 5, length: 2 }],
    },
  },
};
export const state: StudentState = {
  phase: 'ROUND1_OPEN',
  current_application: [],
  enrolled_section_ids: [],
  applicant_counts: { MATH_A: 0, MATH_B: 0, ART_A: 0 },
  remaining: { MATH_A: 1, MATH_B: 2, ART_A: 2 },
  state_version: 0,
  plan_revision: 0,
};
export const plan: Plan = {
  section_ids: ['MATH_A', 'ART_A'],
  preference_score: {
    total: 90,
    details: { course_preference: 90, average_early_days_per_week: 1, time_score: 90 },
  },
  is_complete: true,
  unmet_requirements: {
    required_course_ids: [],
    optional: { mode: 'count', target: 1, achieved: 1, gap: 0 },
  },
  risk: {
    section_probabilities: { MATH_A: 1, ART_A: 1 },
    first_round_all_win_probability: 1,
    first_round_failure_risk: 0,
  },
  fallback: { total: 4, covered: 2, uncovered: 1, unknown: 1, coverage_lower_bound: 0.5, examples: [] },
  recommendation_score: 0.9,
  comparison: null,
  new_section_ids: null,
  explanations: [],
};
export const recommendation: Recommendation = {
  state_version: 0,
  plan_revision: 0,
  purpose: 'initial',
  search_status: 'FOUND',
  searched_nodes: 20,
  decision: 'SHOW_PLANS',
  current_plan: null,
  plans: [plan],
  limitations: [],
};

export const simulationStatus: SimulationStatus = {
  running: false,
  stage: 'idle',
  phase: 'ROUND1_OPEN',
  state_version: 0,
  total_students: 1,
  manual_student: 'S001',
  active_student: null,
  round1_processed: 0,
  round1_submitted: 0,
  round2_processed: 0,
  round2_submitted: 0,
  limited_searches: 0,
  pending_alerts: 0,
  error: null,
  events: [],
};
