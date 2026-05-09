import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { ApiConfigBanner } from "@/components/api-config-banner";
import { Atmosphere } from "@/components/horizon/atmosphere";

export const metadata: Metadata = {
  title: "Bifrost · Command",
  description: "Asgard Aerospace command operating system",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body
        className="relative h-screen overflow-hidden bg-bg text-ink font-sans antialiased"
        data-band="calm"
      >
        <Providers>
          <Atmosphere />
          <ApiConfigBanner />
          <div className="relative z-10 h-full">{children}</div>
        </Providers>
      </body>
    </html>
  );
}
