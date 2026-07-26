import React, { Component } from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { AuthProvider } from './contexts/AuthContext'
import { ToastProvider } from './contexts/ToastContext'
import './styles.css'

class AppErrorBoundary extends Component {
  state = { error: null }

  static getDerivedStateFromError(error) {
    return { error }
  }

  render() {
    if (this.state.error) {
      return <div style={{ color: '#eef0f7', padding: '40px', fontFamily: 'system-ui' }}><h2>Unable to load this page</h2><p>{this.state.error.message}</p></div>
    }
    return this.props.children
  }
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <AppErrorBoundary><React.StrictMode><BrowserRouter><ToastProvider><AuthProvider><App /></AuthProvider></ToastProvider></BrowserRouter></React.StrictMode></AppErrorBoundary>
)
