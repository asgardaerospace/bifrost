import type { Metadata } from "next";
import "./globals.css";
import { Nav } from "@/components/nav";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "Bifrost",
  description: "Asgard Aerospace operating system",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-bg text-ink font-sans">
        <Providers>
          <div className="flex min-h-screen">
            <Nav />
            <main className="flex-1 px-8 py-6">{children}</main>
          </div>
        </Providers>
      </body>
    </html>
  );
}
