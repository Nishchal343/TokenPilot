import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { ChevronLeft, ChevronRight, CircleDollarSign, LayoutDashboard, LogOut, Menu, Network, Sparkles, Users } from 'lucide-react'
import Logo from '../components/Logo'
import NotificationBell from '../components/NotificationBell'
import ProfileDropdown from '../components/ProfileDropdown'
import { useAuth } from '../contexts/AuthContext'

const links = {
  company: [['Dashboard', '/dashboard/company', LayoutDashboard], ['Organization', '/organization', Network], ['Budgets', '/budgets', CircleDollarSign], ['Invitations', '/invitations', Users]],
  manager: [['Dashboard', '/dashboard/team-lead', LayoutDashboard], ['My team', '/organization', Network], ['Team budgets', '/budgets', CircleDollarSign]],
  employee: [['Dashboard', '/dashboard/employee', LayoutDashboard], ['My organization', '/organization', Network], ['My budget', '/budgets', CircleDollarSign]]
}

export default function AppLayout() {
  const { user, profile, logout } = useAuth()
  const [collapsed, setCollapsed] = useState(false)
  const kind = user?.type === 'company' ? 'company' : user?.role === 'manager' ? 'manager' : 'employee'

  return (
    <div className={`app-shell ${collapsed ? 'collapsed' : ''}`}>
      <aside className="sidebar">
        <div className="sidebar-top">
          <Logo compact={collapsed}/>
          <button className="collapse" onClick={() => setCollapsed(!collapsed)}>
            {collapsed ? <ChevronRight size={16}/> : <ChevronLeft size={16}/>}
          </button>
        </div>
        
        <div className="workspace">
          <span className="workspace-mark">{user?.type === 'company' ? 'C' : user?.role === 'manager' ? 'M' : 'E'}</span>
          {!collapsed && (
            <span>
              <b>{user?.type === 'company' ? 'Company workspace' : 'Team workspace'}</b>
              <small>{user?.role || 'admin'}</small>
            </span>
          )}
        </div>
        
        <nav>
          {links[kind].map(([label, path, Icon]) => (
            <NavLink key={path} to={path} className={({isActive}) => isActive ? 'active' : ''}>
              <Icon size={18}/>
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        
        <div className="sidebar-bottom">
          {!collapsed && (
            <div className="upgrade">
              <Sparkles size={17}/>
              <b>AI spend, clarified.</b>
              <small>Connect your future AI stack.</small>
            </div>
          )}
          <button className="nav-button" onClick={() => logout()}>
            <LogOut size={18}/>
            <span>Sign out</span>
          </button>
        </div>
      </aside>
      
      <main className="main">
        <div className="dashboard-top-bar">
          <div className="top-actions">
            <NotificationBell/>
            <ProfileDropdown />
          </div>
        </div>
        
        <div className="content">
          <Outlet/>
        </div>
      </main>
    </div>
  )
}
