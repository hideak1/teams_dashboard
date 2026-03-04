import { useState, useEffect, useRef, useCallback } from 'react'

const API = ''  // same origin

export function useFetch(url, deps = []) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchData = useCallback(() => {
    setLoading(true)
    fetch(API + url)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then(d => { setData(d); setError(null) })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [url])

  useEffect(() => { fetchData() }, [fetchData, ...deps])

  return { data, loading, error, refetch: fetchData }
}

export function useWebSocket(onMessage) {
  const wsRef = useRef(null)

  useEffect(() => {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${proto}//${window.location.host}/ws`)
    wsRef.current = ws

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        onMessage(data)
      } catch {}
    }

    ws.onclose = () => {
      // Reconnect after 3s
      setTimeout(() => {
        if (wsRef.current === ws) {
          wsRef.current = null
        }
      }, 3000)
    }

    return () => { ws.close() }
  }, [])

  return wsRef
}

export function useAutoRefresh(fetchFn, intervalMs = 5000) {
  useEffect(() => {
    const id = setInterval(fetchFn, intervalMs)
    return () => clearInterval(id)
  }, [fetchFn, intervalMs])
}

export function formatTime(ts) {
  if (!ts) return ''
  if (typeof ts === 'number') {
    // Unix timestamp in ms or seconds
    const d = ts > 1e12 ? new Date(ts) : new Date(ts * 1000)
    return d.toLocaleTimeString()
  }
  // ISO string
  return new Date(ts).toLocaleTimeString()
}

export function formatTokens(n) {
  if (!n) return '0'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}
