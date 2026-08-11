import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { ChevronLeft, ChevronRight, LogOut } from 'lucide-react'
import Logo from '../components/Logo'
import NotificationBell from '../components/NotificationBell'
import ProfileDropdown from '../components/ProfileDropdown'
import { useAuth } from '../contexts/AuthContext'
import { navigationByRole } from '../config/navigation'
import './sidebar-utilities.css'

export default function AppLayout() {
  const { user, profile, logout } = useAuth()
  const [collapsed, setCollapsed] = useState(false)
  const kind = user?.type === 'company' ? 'company' : user?.role === 'manager' ? 'manager' : 'employee'
  const managerId = user?.manager_id ?? profile?.manager_id

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

        <div className="sidebar-utilities">
          <NotificationBell/>
          <ProfileDropdown />
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
          {navigationByRole[kind].filter(item => !(item.path === '/dashboard/member/requests' && !managerId)).map(({ label, path, Icon }) => (
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
          <button className="nav-button" onClick={() => logout()} aria-label="Sign out" title={collapsed ? 'Sign out' : undefined}>
            <LogOut size={18}/>
            {!collapsed && <span>Sign out</span>}
          </button>
        </div>
      </aside>
      
      <main className="main">
        <div className="content">
          <Outlet/>
        </div>
      </main>
    </div>
  )
}
