import React, { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useFetch, useWebSocket, useAutoRefresh, formatTime } from '../hooks'

export default function TeamsOverview() {
  const [filter, setFilter] = useState('all')
  const { data: teams, loading, refetch } = useFetch(`/api/teams?filter=${filter}`, [filter])

  // Auto-refresh on WS events
  useWebSocket(useCallback((msg) => {
    if (msg.type === 'team_update' || msg.type === 'team_ended') refetch()
  }, [refetch]))

  useAutoRefresh(refetch, 5000)

  const nav = useNavigate()

  if (loading && !teams) return <div className="loading">Loading teams...</div>

  return (
    <div>
      <div className="page-header">
        <h1>Teams Overview</h1>
        <div className="subtitle">{teams?.length || 0} teams</div>
      </div>

      <div className="filter-bar">
        {['all', 'active', 'ended'].map(f => (
          <button
            key={f}
            className={`filter-btn ${filter === f ? 'active' : ''}`}
            onClick={() => setFilter(f)}
          >
            {f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>

      <div className="card-grid">
        {teams?.map(team => (
          <div
            key={team.name}
            className={`card ${team.active ? 'active' : 'ended'}`}
            onClick={() => nav(`/teams/${team.name}`)}
          >
            <div className="card-title">{team.name}</div>
            <div className="card-desc">{team.description || 'No description'}</div>
            <div className="card-meta">
              <span><StatusDot active={team.active} /> {team.active ? 'Active' : 'Ended'}</span>
              <span>{team.member_count} agents</span>
              <span>{team.task_count} tasks</span>
              <span>{formatTime(team.created_at)}</span>
            </div>
          </div>
        ))}
        {teams?.length === 0 && (
          <div className="loading">No teams found. Start a team in Claude Code to see it here.</div>
        )}
      </div>
    </div>
  )
}

function StatusDot({ active }) {
  return <span className={`status-dot ${active ? 'working' : 'stopped'}`} />
}
