export type GradeStatus = 'correct' | 'incorrect' | 'partial' | 'ungraded' | 'unsupported';

export interface PaperGradeItem {
  item_no: number;
  question: string;
  student_answer: string;
  correct_answer: string;
  status: GradeStatus;
  concept?: string;
}

export interface PaperGradeResponse {
  items: PaperGradeItem[];
  total: number;
  graded: number;
  correct: number;
  incorrect: number;
  ungraded: number;
  collected_mistake_ids?: string[];
  collected_count?: number;
}

export interface ItemDiagnosed {
  concept: string;
  error_type: string;
  explanation?: string;
}

export interface SingleItemGradeResponse {
  graded: {
    status: GradeStatus;
    feedback?: string;
  };
  diagnosed?: ItemDiagnosed | null;
  variants?: string[] | null;
}

export interface QuestionGenParams {
  topic: string;
  difficulty: '初学者' | '中等' | '拔高';
  count: number;
  question_type: 'choice' | 'fill' | 'qa' | 'mixed';
}

export interface QuizGradeResponse {
  feedback: string;
}
