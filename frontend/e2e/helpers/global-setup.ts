/**
 * Refuses to run the mutating E2E suite unless explicitly opted in.
 * CI sets E2E_ALLOW_MUTATION=true against its ephemeral database; locally the
 * operator must opt in knowingly because the suite creates and deletes real
 * workspace data on the targeted stack.
 */
export default async function globalSetup(): Promise<void> {
  if (process.env.E2E_ALLOW_MUTATION !== "true") {
    throw new Error(
      "This E2E suite mutates workspace data (jobs, resumes, applications). "
        + "Set E2E_ALLOW_MUTATION=true to acknowledge this. CI runs set it "
        + "against an ephemeral database that is destroyed afterwards."
    );
  }
}
