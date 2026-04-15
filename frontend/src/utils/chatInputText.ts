export const appendTranscribedTextToInput = (
  currentInput: string,
  transcribedText: string,
): string => {
  if (!currentInput) {
    return transcribedText;
  }

  const needsSpaceSeparator =
    !/\s$/.test(currentInput) && !/^\s/.test(transcribedText);

  return needsSpaceSeparator
    ? `${currentInput} ${transcribedText}`
    : `${currentInput}${transcribedText}`;
};
