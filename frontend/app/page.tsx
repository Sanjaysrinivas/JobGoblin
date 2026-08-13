import { redirect } from "next/navigation";

// The root simply forwards into the workspace. Auth gating happens at the
// backend session layer once both branches merge.
export default function Home() {
  redirect("/dashboard");
}
