import BinanceLayout from "@/components/BinanceLayout"
import { MockProvider } from '@/context/RiskContext'
import LiveRiskProvider from '@/context/LiveRiskContext'
import EventLog from '@/components/EventLog'

export default function InstitutionalPage() {
  return (
    <MockProvider>
      <LiveRiskProvider>
        <div style={{ display: 'flex', gap: 12 }}>
          <div style={{ flex: 1 }}>
            <BinanceLayout />
          </div>
          <div style={{ width: 380 }}>
            <EventLog />
          </div>
        </div>
      </LiveRiskProvider>
    </MockProvider>
  )
}
