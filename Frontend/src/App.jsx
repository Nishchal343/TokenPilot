import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth, roleHome } from './contexts/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
import GuestRoute from './components/GuestRoute'
import AppLayout from './layouts/AppLayout'
import Loading from './components/Loading'

// Keep page code out of the initial bundle. This prevents Vite's large-chunk
// warning and makes the first screen load faster.
const Landing = lazy(() => import('./pages/Landing'))
const Auth = lazy(() => import('./pages/Auth'))
const Dashboard = lazy(() => import('./pages/Dashboard'))
const Organization = lazy(() => import('./pages/Organization'))
const Budgets = lazy(() => import('./pages/Budgets'))
const Profile = lazy(() => import('./pages/Profile'))
const Settings = lazy(() => import('./pages/Settings'))
const Notifications = lazy(() => import('./pages/Notifications'))
const Security = lazy(() => import('./pages/Security'))
const HelpCenter = lazy(() => import('./pages/HelpCenter'))
const Documentation = lazy(() => import('./pages/Documentation'))
const Invitations = lazy(() => import('./pages/Invitations'))
const InvitationAccept = lazy(() => import('./pages/InvitationAccept'))

function Home() { const {isAuthenticated,user,initialized}=useAuth(); if (!initialized) return <Loading/>; return <Navigate to={isAuthenticated?roleHome(user):'/home'} replace/> }
function HomeRoute() { const {isAuthenticated,user,initialized}=useAuth(); if (!initialized) return <Loading/>; if (isAuthenticated) return <Navigate to={roleHome(user)} replace/>; return <Landing/> }

export default function App() {
  return (
    <Suspense fallback={<Loading/>}>
      <Routes>
      <Route path="/" element={<Home/>}/>
      <Route path="/home" element={<HomeRoute/>}/>
      <Route path="/invitation/:token" element={<InvitationAccept/>}/>
      
      <Route element={<GuestRoute/>}>
        <Route path="/login" element={<Auth mode="login"/>}/>
        <Route path="/register" element={<Auth mode="register"/>}/>
        <Route path="/verify" element={<Auth mode="verify"/>}/>
        <Route path="/forgot" element={<Auth mode="forgot"/>}/>
        <Route path="/reset" element={<Auth mode="reset"/>}/>
      </Route>
      
      <Route element={<ProtectedRoute/>}>
        <Route element={<AppLayout/>}>
          <Route path="/dashboard/company" element={<Role role="company"><Dashboard type="company"/></Role>}/>
          <Route path="/dashboard/team-lead" element={<Role role="manager"><Dashboard type="manager"/></Role>}/>
          <Route path="/dashboard/employee" element={<Role role="employee"><Dashboard type="employee"/></Role>}/>
          <Route path="/organization" element={<Organization/>}/>
          <Route path="/budgets" element={<Budgets/>}/>
          <Route path="/invitations" element={<Invitations/>}/>
          <Route path="/profile" element={<Profile/>}/>
          <Route path="/settings" element={<Settings/>}/>
          <Route path="/notifications" element={<Notifications/>}/>
          <Route path="/security" element={<Security/>}/>
          <Route path="/help" element={<HelpCenter/>}/>
          <Route path="/docs" element={<Documentation/>}/>
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace/>}/>
      </Routes>
    </Suspense>
  )
}

function Role({role,children}) { const {user}=useAuth(); const actual=user?.type==='company'?'company':user?.role; return actual===role?children:<Navigate to={roleHome(user)} replace/> }
