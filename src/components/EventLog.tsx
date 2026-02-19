import React from 'react'
import { RiskEvent, useLiveRisk } from '../context/LiveRiskContext'

const EventRow: React.FC<{ ev: RiskEvent }> = ({ ev }) => {
  return (
    <div style={{ borderBottom: '1px solid rgba(0,0,0,0.06)', padding: '8px 0' }}>
      <div style={{ fontSize: 12, color: '#666' }}>{new Date(ev.time || Date.now()).toLocaleString()}</div>
      <div style={{ fontWeight: 600 }}>{ev.type} {ev.trace_id ? `· ${ev.trace_id}` : ''}</div>
      <div style={{ fontSize: 13 }}>{ev.message || JSON.stringify(ev.payload || '')}</div>
    </div>
  )
}

export const EventLog: React.FC<{ limit?: number }> = ({ limit = 100 }) => {
  const { events, connected } = useLiveRisk()

  return (
    <div style={{ border: '1px solid rgba(0,0,0,0.08)', padding: 12, borderRadius: 6, maxHeight: 420, overflow: 'auto' }}>
      <div style={{ marginBottom: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <strong>Event Log</strong>
        <span style={{ fontSize: 12, color: connected ? 'green' : 'orange' }}>{connected ? 'CONNECTED' : 'DISCONNECTED'}</span>
      </div>
      {events.slice(0, limit).map((ev, idx) => <EventRow key={idx} ev={ev} />)}
      {events.length === 0 && <div style={{ color: '#888', padding: 12 }}>No events yet</div>}
    </div>
  )
}

export default EventLog
