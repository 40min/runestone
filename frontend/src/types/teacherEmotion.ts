export const TEACHER_EMOTIONS = [
  "neutral",
  "happy",
  "sad",
  "worried",
  "concerned",
  "thinking",
  "hopeful",
  "surprised",
  "serious",
] as const;

export type TeacherEmotion = (typeof TEACHER_EMOTIONS)[number];

export const normalizeTeacherEmotion = (
  value?: string | null,
): TeacherEmotion => {
  return TEACHER_EMOTIONS.includes(value as TeacherEmotion)
    ? (value as TeacherEmotion)
    : "neutral";
};
