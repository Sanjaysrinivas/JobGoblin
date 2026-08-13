import { api } from "@/lib/api";
import type { UserProfile, UserProfilePayload } from "@/lib/types";

export function getProfile(): Promise<UserProfile> {
  return api.get<UserProfile>("/profile");
}

export function saveProfile(payload: UserProfilePayload): Promise<UserProfile> {
  return api.put<UserProfile>("/profile", payload);
}

export function seedProfileFromResume(resumeId: string): Promise<UserProfile> {
  return api.post<UserProfile>("/profile/seed", { resume_id: resumeId });
}

export function deleteProfile(): Promise<void> {
  return api.delete<void>("/profile");
}