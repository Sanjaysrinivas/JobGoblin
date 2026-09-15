/**
 * Shared resume/cover-letter selection rules. Both the create and edit
 * application forms route through these so the pairing invariants hold
 * everywhere: letters belong to one job, each letter links one resume, and a
 * letter may only stay selected while its own resume is selected.
 */

export interface SelectableCoverLetter {
  id: string;
  job_id: string;
  resume_id: string;
}

export function lettersForJob<T extends SelectableCoverLetter>(letters: T[], jobId: string): T[] {
  return letters.filter((letter) => letter.job_id === jobId);
}

/** Selecting a letter derives its linked resume; otherwise keep the current one. */
export function resumeForLetter<T extends SelectableCoverLetter>(
  letters: T[],
  letterId: string,
  fallbackResumeId: string
): string {
  const letter = letters.find((item) => item.id === letterId);
  return letter ? letter.resume_id : fallbackResumeId;
}

/** Changing the resume drops any letter linked to a different resume. */
export function letterForResume<T extends SelectableCoverLetter>(
  letters: T[],
  letterId: string,
  resumeId: string
): string {
  const letter = letters.find((item) => item.id === letterId);
  return letter && letter.resume_id !== resumeId ? "" : letterId;
}
