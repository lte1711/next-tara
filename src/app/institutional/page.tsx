import BinanceLayout from "@/components/BinanceLayout"
import { MockProvider } from '@/context/RiskContext'

export default function InstitutionalPage() {
  return (
    <MockProvider>
      <BinanceLayout />
    </MockProvider>
  )
}
