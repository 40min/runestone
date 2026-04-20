// User data interface matching backend User model
export interface UserData {
  id: number;
  email: string;
  name: string | null;
  surname: string | null;
  telegram_username?: string | null;
  mother_tongue?: string | null;
  timezone: string | null;
  pages_recognised_count: number;
  personal_info?: Record<string, unknown> | null;
  areas_to_improve?: Record<string, unknown> | null;
  knowledge_strengths?: Record<string, unknown> | null;
}
