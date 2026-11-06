export type MistakeStatus = 'pending' | 'confirmed' | 'dismissed';

export interface MistakeItem {
  id: string;
  user_id: string;
  subject: string;
  concept: string;
  error_type: string;
  question_text: string;
  student_answer: string;
  correct_answer: string;
  analysis?: string;
  created_at: string;
  status: MistakeStatus;
  repetitions: number;
  interval_days: number;
  ease: number;
  next_review_at: string | null;
  review_count?: number;
}

export interface ReviewResponse {
  id: string;
  ease: number;
  interval_days: number;
  repetitions: number;
  review_count: number;
  next_review_at: string;
}

export interface RescheduleResponse {
  id: string;
  when_text: string;
}

export interface MasteryItem {
  user_id: string;
  concept: string;
  score: number;
  attempts: number;
  last_seen: string;
}

export interface CreateMistakePayload {
  user_id?: string;
  subject: string;
  concept: string;
  error_type: string;
  question_text: string;
  student_answer: string;
  correct_answer: string;
  analysis?: string;
}
