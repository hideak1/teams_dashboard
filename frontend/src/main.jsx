import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom'
import TeamsOverview from './pages/TeamsOverview'
import TeamDetail from './pages/TeamDetail'
import AgentDetail from './pages/AgentDetail'
import GlobalStats from './pages/GlobalStats'
import './style.css'

function Nav() {
  const loc = useLocation()
  const links = [
    { to: '/', label: 'Teams' },
    { to: '/stats', label: 'Global Stats' },
  ]
  return (
    <nav className="nav">
      <div className="nav-brand">Team Dashboard</div>
      <div className="nav-links">
        {links.map(l => (
          <Link key={l.to} to={l.to} className={loc.pathname === l.to ? 'active' : ''}>
            {l.label}
          </Link>
        ))}
      </div>
    </nav>
  )
}

function App() {
  return (
    <BrowserRouter>
      <Nav />
      <main className="main">
        <Routes>
          <Route path="/" element={<TeamsOverview />} />
          <Route path="/teams/:name" element={<TeamDetail />} />
          <Route path="/agents/:agentId" element={<AgentDetail />} />
          <Route path="/stats" element={<GlobalStats />} />
        </Routes>
      </main>
    </BrowserRouter>
  )
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />)
