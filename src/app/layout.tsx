import { buildTokenCss } from "@/theme/tokens";
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NEXT-TRADE Command Center",
  description: "Real-time trading dashboard",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-bg text-text">
        <style dangerouslySetInnerHTML={{ __html: buildTokenCss() }} />
        {children}
      </body>
    </html>
  );
}
