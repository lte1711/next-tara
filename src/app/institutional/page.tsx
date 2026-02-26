export const dynamic = "force-dynamic";
export const revalidate = 0;

import BinanceLayout from "@/components/BinanceLayout";
import EventLog from "@/components/EventLog";
import LiveRiskProvider from "@/context/LiveRiskContext";
import { MockProvider } from "@/context/RiskContext";

export default function InstitutionalPage() {
  return (
    <MockProvider>
      <LiveRiskProvider>
        <div style={{ display: "flex", gap: 12 }}>
          <div style={{ flex: 1 }}>
            <BinanceLayout />
          </div>
          <div style={{ width: 380 }}>
            <EventLog />
          </div>
        </div>
      </LiveRiskProvider>
    </MockProvider>
  );
}
