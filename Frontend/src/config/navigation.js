import { CircleDollarSign, LayoutDashboard, Network, Sparkles, Users, ClipboardList } from 'lucide-react'

export const navigationByRole = {
  company: [
    { label: 'Dashboard', path: '/dashboard/company', Icon: LayoutDashboard },
    { label: 'Teams', path: '/dashboard/company/teams', Icon: Network },
    { label: 'Budget Approval', path: '/dashboard/company/budget-approval', Icon: CircleDollarSign },
    { label: 'Invitations', path: '/dashboard/company/invitations', Icon: Users },
    { label: 'AI Workspace', path: '/dashboard/company/ai-workspace', Icon: Sparkles }
  ],
  manager: [
    { label: 'Dashboard', path: '/dashboard/team-leader', Icon: LayoutDashboard },
    { label: 'My Team', path: '/dashboard/team-leader/my-team', Icon: Network },
    { label: 'Team Budget', path: '/dashboard/team-leader/team-budget', Icon: CircleDollarSign },
    { label: 'AI Workspace', path: '/dashboard/team-leader/ai-workspace', Icon: Sparkles }
  ],
  employee: [
    { label: 'Dashboard', path: '/dashboard/member', Icon: LayoutDashboard },
    { label: 'Requests', path: '/dashboard/member/requests', Icon: ClipboardList },
    { label: 'AI Workspace', path: '/dashboard/member/ai-workspace', Icon: Sparkles }
  ]
}
