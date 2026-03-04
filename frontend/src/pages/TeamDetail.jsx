import React, { useCallback, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useFetch, useWebSocket, useAutoRefresh, formatTime, formatTokens } from '../hooks'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

export default function TeamDetail() {
  const { name } = useParams()
  const nav = useNavigate()
  const { data, loading, refetch } = useFetch(`/api/teams/${name}`)

  useWebSocket(useCallback((msg) => {
    if (msg.team === name) refetch()
  }, [name, refetch]))

  useAutoRefresh(refetch, 5000)

  if (loading && !data) return <div className="loading">Loading team...</div>
  if (!data || data.error) return <div className="error">Team not found</div>

  const { agents = [], tasks = [], messages = [], token_stats = [] } = data

  const pending = tasks.filter(t => t.status === 'pending')
  const inProgress = tasks.filter(t => t.status === 'in_progress')
  const completed = tasks.filter(t => t.status === 'completed')

  const tokenData = token_stats.map(s => ({
    name: s.agent_name || 'unknown',
    tokens: s.total_tokens || 0,
  }))

  const recentMessages = messages.slice(0, 50)

  return (
    <div>
      <div className="page-header">
        <h1>{name}</h1>
        <div className="subtitle">
          {data.description || 'No description'}
          <span style={{ marginLeft: 16, color: data.active ? 'var(--green)' : 'var(--text-dim)' }}>
            {data.active ? 'Active' : 'Ended'}
          </span>
        </div>
      </div>

      {/* Agents */}
      <div className="section">
        <div className="section-title">Agents ({agents.length})</div>
        <div className="agent-list">
          {agents.map(a => (
            <div
              key={a.agent_id}
              className="agent-chip"
              onClick={() => nav(`/agents/${encodeURIComponent(a.agent_id)}`)}
            >
              <span className={`status-dot ${a.status || 'idle'}`} />
              <span>{a.name}</span>
              <span className="model">{a.model}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Task board */}
      <div className="section">
        <div className="section-title">Tasks ({tasks.length})</div>
        <div className="task-columns">
          <div>
            <div className="task-column-title">Pending ({pending.length})</div>
            {pending.map(t => <TaskItem key={t.task_id} task={t} />)}
          </div>
          <div>
            <div className="task-column-title">In Progress ({inProgress.length})</div>
            {inProgress.map(t => <TaskItem key={t.task_id} task={t} />)}
          </div>
          <div>
            <div className="task-column-title">Completed ({completed.length})</div>
            {completed.map(t => <TaskItem key={t.task_id} task={t} />)}
          </div>
        </div>
      </div>

      {/* Token chart */}
      {tokenData.length > 0 && (
        <div className="section">
          <div className="section-title">Token Usage (per agent)</div>
          <div className="chart-container" style={{ height: 260 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={tokenData}>
                <XAxis dataKey="name" tick={{ fill: '#8888a0', fontSize: 12 }} />
                <YAxis tick={{ fill: '#8888a0', fontSize: 12 }} tickFormatter={formatTokens} />
                <Tooltip
                  contentStyle={{ background: '#12121a', border: '1px solid #1e1e2e', borderRadius: 8 }}
                  labelStyle={{ color: '#e0e0e8' }}
                  formatter={(v) => [`≈ ${formatTokens(v)}`, 'Tokens']}
                />
                <Bar dataKey="tokens" fill="#6c5ce7" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Inbox */}
      <div className="section">
        <div className="section-title">Inbox ({messages.length})</div>
        <div className="inbox-list">
          {recentMessages.map((m, i) => (
            <ExpandableMessage key={i} msg={m} />
          ))}
          {messages.length === 0 && <div className="loading">No messages yet</div>}
        </div>
      </div>
    </div>
  )
}

function ExpandableMessage({ msg }) {
  const [expanded, setExpanded] = useState(false)
  const preview = msg.summary || (msg.text?.length > 160 ? msg.text.slice(0, 160) + '...' : msg.text)

  return (
    <div className="expandable-msg" onClick={() => setExpanded(!expanded)}>
      <div className="expandable-msg-header">
        <span className="msg-from">{msg.from_agent || '?'}</span>
        <span className="msg-arrow">&rarr;</span>
        <span className="msg-to">{msg.agent_name || '?'}</span>
        <span className="msg-preview">{expanded ? '' : preview}</span>
        <span className="msg-time">{formatTime(msg.timestamp)}</span>
      </div>
      {expanded && <div className="expandable-msg-body">{msg.text}</div>}
    </div>
  )
}

function TaskItem({ task }) {
  return (
    <div className={`task-item status-${task.status}`}>
      <div>#{task.task_id} {task.subject}</div>
      {task.owner && <div className="task-owner">{task.owner}</div>}
    </div>
  )
}
