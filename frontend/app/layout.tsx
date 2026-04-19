import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { ApiConfigBanner } from "@/components/api-config-banner";

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
      <body className="h-screen overflow-hidden bg-bg text-ink font-sans antialiased">
        <Providers>
          <ApiConfigBanner />
          {children}
        </Providers>
      </body>
    </html>
  );
}
