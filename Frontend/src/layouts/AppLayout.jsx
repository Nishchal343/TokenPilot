import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { ChevronLeft, ChevronRight, LogOut, Sparkles } from 'lucide-react'
import Logo from '../components/Logo'
import NotificationBell from '../components/NotificationBell'
import ProfileDropdown from '../components/ProfileDropdown'
import { useAuth } from '../contexts/AuthContext'
import { navigationByRole } from '../config/navigation'

export default function AppLayout() {
  const { user, profile, logout } = useAuth()
  const [collapsed, setCollapsed] = useState(false)
  const kind = user?.type === 'company' ? 'company' : user?.role === 'manager' ? 'manager' : 'employee'

  return (
    <div className={`app-shell ${collapsed ? 'collapsed' : ''}`}>
      <aside className="sidebar">
        <div className="sidebar-top">
          <Logo compact={collapsed}/>
          <button
            className="collapse"
            onClick={() => setCollapsed(!collapsed)}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {collapsed ? <ChevronRight size={16}/> : <ChevronLeft size={16}/>}
          </button>
        </div>
        
        {!collapsed && (
          <div className="workspace">
            <span className="workspace-mark">{user?.type === 'company' ? 'C' : user?.role === 'manager' ? 'M' : 'E'}</span>
            <span>
              <b>{user?.type === 'company' ? 'Company workspace' : 'Team workspace'}</b>
              <small>{user?.role || 'admin'}</small>
            </span>
          </div>
        )}
        
        <nav>
          {navigationByRole[kind].map(({ label, path, Icon }) => (
            <NavLink
              key={path}
              to={path}
              end={path === navigationByRole[kind][0].path}
              className={({isActive}) => isActive ? 'active' : ''}
              aria-label={label}
              title={collapsed ? label : undefined}
            >
              <Icon size={18}/>
              {!collapsed && <span>{label}</span>}
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
          <button className="nav-button" onClick={() => logout()} aria-label="Sign out" title={collapsed ? 'Sign out' : undefined}>
            <LogOut size={18}/>
            {!collapsed && <span>Sign out</span>}
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
