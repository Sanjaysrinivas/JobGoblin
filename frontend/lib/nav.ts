import {
  LayoutDashboard,
  FileText,
  Briefcase,
  ClipboardList,
  MessageSquareText,
  UserRound,
  Users,
  Settings,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  title: string;
  href: string;
  icon: LucideIcon;
  description: string;
}

/** Primary application navigation (design.md section 13). */
export const navItems: NavItem[] = [
  {
    title: "Dashboard",
    href: "/dashboard",
    icon: LayoutDashboard,
    description: "Pipeline overview and recent activity",
  },
  {
    title: "Resumes",
    href: "/resumes",
    icon: FileText,
    description: "Upload, parse, and manage resume versions",
  },
  {
    title: "Profile",
    href: "/profile",
    icon: UserRound,
    description: "Master profile from your own resume facts",
  },
  {
    title: "Jobs",
    href: "/jobs",
    icon: Briefcase,
    description: "Saved roles and resume-to-job analysis",
  },
  {
    title: "Applications",
    href: "/applications",
    icon: ClipboardList,
    description: "Track every application from saved to offer",
  },
  {
    title: "Contacts",
    href: "/contacts",
    icon: Users,
    description: "Recruiters and referrals for outreach",
  },
  {
    title: "Outreach",
    href: "/outreach",
    icon: MessageSquareText,
    description: "Review local drafts before copying",
  },
  {
    title: "Settings",
    href: "/settings",
    icon: Settings,
    description: "Account, AI provider, and preferences",
  },
];
