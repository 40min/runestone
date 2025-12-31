// User data interface matching backend User model
export interface UserData {
  id: number;
  email: string;
  name: string | null;
  surname: string | null;
  timezone: string | null;
  pages_recognised_count: number;
  words_in_learn_count?: number;
  words_learned_count?: number;
  words_skipped_count: number;
  overall_words_count: number;
}
