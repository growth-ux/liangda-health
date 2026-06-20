// 镜像 backend/app/schemas/agent_response.py
// 改 Pydantic 时务必同步改这里

export type ResponseKind =
  | 'meal_plan'
  | 'qa'
  | 'greeting'
  | 'kb_interpretation'
  | 'general_advice';

export type MealSlot = 'breakfast' | 'lunch' | 'dinner';

export interface MealItem {
  slot: MealSlot | null;
  title: string;
  summary: string;
}

export interface MemberAdjustment {
  member_name: string;
  note: string;
  tags: string[];
}

export interface MealPlanPayload {
  scope: 'family' | 'member';
  target_member_name: string | null;
  meal_items: MealItem[];
  member_adjustments: MemberAdjustment[];
  avoid_tags: string[];
  extra_note: string | null;
}

export interface QaPayload {
  question_topic: string;
  answer: string;
  tips: string[];
}

export interface GreetingPayload {
  message: string;
  suggested_topics: string[];
}

export type EvidenceType = 'report_fact' | 'device' | 'memory' | 'product';

export interface EvidenceItem {
  type: EvidenceType;
  title: string;
  excerpt: string;
  source_id: string;
  source_label: string;
}

export interface MessageEvidence {
  content_items: EvidenceItem[];
  product_items: EvidenceItem[];
}

export interface SuggestionItem {
  text: string;
  priority: 'primary' | 'secondary';
}

export interface KbInterpretationPayload {
  topic: string;
  evidence: EvidenceItem[];
  suggestions: SuggestionItem[];
  red_flags: string[];
}

export interface GeneralAdvicePayload {
  topic: string;
  advice: string;
  cautions: string[];
}

export type PayloadUnion =
  | MealPlanPayload
  | QaPayload
  | GreetingPayload
  | KbInterpretationPayload
  | GeneralAdvicePayload;

export interface StructuredResponse<K extends ResponseKind = ResponseKind> {
  kind: K;
  summary_text: string;
  payload: K extends 'meal_plan' ? MealPlanPayload
    : K extends 'qa' ? QaPayload
    : K extends 'greeting' ? GreetingPayload
    : K extends 'kb_interpretation' ? KbInterpretationPayload
    : GeneralAdvicePayload;
  evidence?: MessageEvidence | null;
}

// 简化版：前端大多数场景只关心 kind + summary_text + payload，松类型即可
export type StructuredCard = {
  kind: ResponseKind;
  summary_text: string;
  payload: PayloadUnion;
  evidence?: MessageEvidence | null;
};
