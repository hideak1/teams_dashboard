import React, { useCallback, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useFetch, useWebSocket, useAutoRefresh, formatTime, formatTokens } from '../hooks'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

export default function AgentDetail() {
  const { agentId } = useParams()
  const { data, loading, refetch } = useFetch(`/api/agents/${agentId}`)

  useWebSocket(useCallback((msg) => {
    if (msg.agent === data?.agent?.name) refetch()
  }, [data?.agent?.name, refetch]))

  useAutoRefresh(refetch, 5000)

  if (loading && !data) return <div className="loading">Loading agent...</div>
  if (!data || data.error) return <div className="error">Agent not found</div>

  const { agent, events = [], tasks = [], messages = [] } = data

  // Build token timeline from events
  const tokenTimeline = []
  let cumulative = 0
  const sortedEvents = [...events].reverse()
  for (const e of sortedEvents) {
    if (e.estimated_tokens > 0) {
      cumulative += e.estimated_tokens
      tokenTimeline.push({
        time: formatTime(e.created_at),
        tokens: cumulative,
      })
    }
  }

  const toolEvents = events.filter(e => e.tool_name)

  const statusColor = { pending: 'var(--text-dim)', in_progress: 'var(--yellow)', completed: 'var(--green)' }

  return (
    <div>
      <div className="page-header">
        <h1>{agent.name}</h1>
        <div className="subtitle">
          <span className={`status-dot ${agent.status || 'idle'}`} style={{ marginRight: 8 }} />
          {agent.agent_type} &middot; {agent.model} &middot; {agent.team_name}
        </div>
      </div>

      {/* Stats */}
      <div className="stat-grid">
        <div className="stat-card">
          <div className="stat-value">&asymp; {formatTokens(agent.estimated_tokens)}</div>
          <div className="stat-label">Estimated Tokens</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{events.length}</div>
          <div className="stat-label">Events</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{toolEvents.length}</div>
          <div className="stat-label">Tool Uses</div>
        </div>
      </div>

      {/* Assigned Tasks */}
      {tasks.length > 0 && (
        <div className="section">
          <div className="section-title">Assigned Tasks ({tasks.length})</div>
          <div className="agent-task-list">
            {tasks.map(t => (
              <div key={t.task_id} className="agent-task-item" style={{ borderLeftColor: statusColor[t.status] || 'var(--text-dim)' }}>
                <span className="agent-task-id">#{t.task_id}</span>
                <span className="agent-task-subject">{t.subject}</span>
                <span className={`agent-task-status status-${t.status}`}>{t.status}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Messages */}
      {messages.length > 0 && (
        <div className="section">
          <div className="section-title">Messages ({messages.length})</div>
          <div className="inbox-list">
            {messages.map((m, i) => (
              <MessageItem key={i} msg={m} agentName={agent.name} />
            ))}
          </div>
        </div>
      )}

      {/* Token chart */}
      {tokenTimeline.length > 1 && (
        <div className="section">
          <div className="section-title">Token Usage Over Time</div>
          <div className="chart-container" style={{ height: 240 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={tokenTimeline}>
                <XAxis dataKey="time" tick={{ fill: '#8888a0', fontSize: 11 }} />
                <YAxis tick={{ fill: '#8888a0', fontSize: 11 }} tickFormatter={formatTokens} />
                <Tooltip
                  contentStyle={{ background: '#12121a', border: '1px solid #1e1e2e', borderRadius: 8 }}
                  formatter={(v) => [`≈ ${formatTokens(v)}`, 'Cumulative']}
                />
                <Line type="monotone" dataKey="tokens" stroke="#6c5ce7" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Event timeline */}
      <div className="section">
        <div className="section-title">Recent Events</div>
        <ul className="timeline">
          {events.slice(0, 100).map((e, i) => (
            <li key={i} className="timeline-item">
              <span className="tl-time">{formatTime(e.created_at)}</span>
              <span className="tl-event" style={{ color: eventColor(e.hook_event) }}>
                {e.hook_event}
              </span>
              <span className="tl-detail">
                {e.tool_name && `${e.tool_name} `}
                {e.estimated_tokens > 0 && `≈${formatTokens(e.estimated_tokens)} tokens`}
              </span>
            </li>
          ))}
          {events.length === 0 && <div className="loading">No events recorded</div>}
        </ul>
      </div>
    </div>
  )
}

function MessageItem({ msg, agentName }) {
  const [expanded, setExpanded] = useState(false)
  const isIncoming = msg.agent_name === agentName
  const direction = isIncoming ? 'incoming' : 'outgoing'
  const arrow = isIncoming ? '\u2190' : '\u2192'
  const peer = isIncoming ? msg.from_agent : msg.agent_name
  const preview = msg.summary || (msg.text?.length > 120 ? msg.text.slice(0, 120) + '...' : msg.text)

  return (
    <div className={`expandable-msg ${direction}`} onClick={() => setExpanded(!expanded)}>
      <div className="expandable-msg-header">
        <span className={`msg-direction ${direction}`}>{arrow}</span>
        <span className="msg-peer">{peer || '?'}</span>
        <span className="msg-preview">{expanded ? '' : preview}</span>
        <span className="msg-time">{formatTime(msg.timestamp)}</span>
      </div>
      {expanded && <div className="expandable-msg-body">{msg.text}</div>}
    </div>
  )
}

function eventColor(event) {
  const colors = {
    SessionStart: '#00d68f',
    SessionEnd: '#ff6b6b',
    PreToolUse: '#f0c040',
    PostToolUse: '#4da6ff',
    Stop: '#ff6b6b',
  }
  return colors[event] || '#8888a0'
}
