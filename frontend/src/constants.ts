/**
 * Constants for vocabulary improvement modes.
 * These should match the ImprovementMode enum in the backend.
 */
export const VOCABULARY_IMPROVEMENT_MODES = {
  EXAMPLE_ONLY: 'example_only',
  EXTRA_INFO_ONLY: 'extra_info_only',
  ALL_FIELDS: 'all_fields',
} as const;

export type VocabularyImprovementMode = typeof VOCABULARY_IMPROVEMENT_MODES[keyof typeof VOCABULARY_IMPROVEMENT_MODES];
