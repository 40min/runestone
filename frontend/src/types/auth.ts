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
}
