import type { Metadata } from "next";

import { ProfileBuilderView } from "@/components/profile/profile-builder-view";

export const metadata: Metadata = { title: "Profile" };

export default function ProfilePage() {
  return <ProfileBuilderView />;
}
