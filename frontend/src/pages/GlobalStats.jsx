import React, { useCallback } from 'react'
import { useFetch, useWebSocket, useAutoRefresh, formatTokens } from '../hooks'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line } from 'recharts'

export default function GlobalStats() {
  const { data: stats, refetch: refetchStats } = useFetch('/api/stats')
  const { data: tokenStats, refetch: refetchTokens } = useFetch('/api/tokens/timeline?bucket=300')
  const { data: leaderboard } = useFetch('/api/events?limit=0')

  // Token leaderboard from events endpoint grouped by agent
  const { data: agentStats, refetch: refetchAgents } = useFetch('/api/teams')

  useWebSocket(useCallback(() => {
    refetchStats()
    refetchTokens()
  }, [refetchStats, refetchTokens]))

  useAutoRefresh(refetchStats, 10000)

  if (!stats) return <div className="loading">Loading stats...</div>

  // Build timeline data
  const timeline = (tokenStats || []).map(b => ({
    time: new Date(b.bucket * 1000).toLocaleTimeString(),
    tokens: b.tokens,
    agent: b.agent_name,
  }))

  // Build leaderboard from all teams' agents
  const allAgents = []
  if (agentStats) {
    // We'd need a separate endpoint, but let's use token stats
  }

  return (
    <div>
      <div className="page-header">
        <h1>Global Statistics</h1>
      </div>

      {/* Stat cards */}
      <div className="stat-grid">
        <div className="stat-card">
          <div className="stat-value">{stats.total_teams}</div>
          <div className="stat-label">Total Teams</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats.active_teams}</div>
          <div className="stat-label">Active Teams</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats.total_agents}</div>
          <div className="stat-label">Total Agents</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats.completed_tasks}/{stats.total_tasks}</div>
          <div className="stat-label">Tasks Completed</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">&asymp; {formatTokens(stats.total_estimated_tokens)}</div>
          <div className="stat-label">Est. Tokens</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">${stats.estimated_cost_sonnet?.toFixed(2)}</div>
          <div className="stat-label">Est. Cost (Sonnet)</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">${stats.estimated_cost_opus?.toFixed(2)}</div>
          <div className="stat-label">Est. Cost (Opus)</div>
        </div>
      </div>

      {/* Timeline chart */}
      {timeline.length > 0 && (
        <div className="section">
          <div className="section-title">Token Usage Timeline</div>
          <div className="chart-container" style={{ height: 280 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={timeline}>
                <XAxis dataKey="time" tick={{ fill: '#8888a0', fontSize: 11 }} />
                <YAxis tick={{ fill: '#8888a0', fontSize: 11 }} tickFormatter={formatTokens} />
                <Tooltip
                  contentStyle={{ background: '#12121a', border: '1px solid #1e1e2e', borderRadius: 8 }}
                  formatter={(v) => [`≈ ${formatTokens(v)}`, 'Tokens']}
                />
                <Bar dataKey="tokens" fill="#6c5ce7" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  )
}
