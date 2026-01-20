/**
 * Generates a unique ID using crypto.randomUUID() if available,
 * otherwise falls back to a pseudo-random string.
 *
 * crypto.randomUUID() is only available in secure contexts (HTTPS).
 */
export const generateId = (): string => {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }

  // Fallback for non-secure contexts
  return Math.random().toString(36).substring(2, 11) +
         Date.now().toString(36);
};
