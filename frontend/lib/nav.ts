import {
  LayoutDashboard,
  FileText,
  Briefcase,
  ClipboardList,
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

/** Primary application navigation (design.md §13). */
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
    title: "Settings",
    href: "/settings",
    icon: Settings,
    description: "Account, AI provider, and preferences",
  },
];
