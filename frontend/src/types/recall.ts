export interface RecallWord {
  id: number;
  word_phrase: string;
  translation?: string | null;
  example_phrase?: string | null;
}

export interface RecallState {
  configured: boolean;
  delivery_enabled: boolean;
  recall_start_hour: number;
  recall_end_hour: number;
  timezone: string;
  words: RecallWord[];
}

export type RecallPendingAction =
  | { type: "refresh" }
  | { type: "postpone"; vocabularyId: number }
  | { type: "remove"; vocabularyId: number }
  | { type: "saveSettings" }
  | { type: "toggleDelivery"; enabled: boolean };
