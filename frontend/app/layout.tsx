import type { Metadata } from "next";
import { CopilotKit } from "@copilotkit/react-core";
import "@copilotkit/react-ui/styles.css";
import "./globals.css";
import { ModeProvider } from "./contexts/ModeContext";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "AusLaw AI - Australian Legal Assistant",
    template: "%s | AusLaw AI",
  },
  description:
    "Get instant answers about Australian law, find qualified lawyers, and receive step-by-step legal guidance across all states and territories.",
  keywords: [
    "Australian law",
    "legal assistant",
    "legal advice Australia",
    "find lawyer Australia",
    "NSW law",
    "QLD law",
    "Australian legal rights",
  ],
  authors: [{ name: "AusLaw AI" }],
  openGraph: {
    type: "website",
    locale: "en_AU",
    siteName: "AusLaw AI",
    title: "AusLaw AI - Australian Legal Assistant",
    description:
      "Get instant answers about Australian law, find qualified lawyers, and receive step-by-step legal guidance across all states and territories.",
    images: [
      {
        url: "/icon.png",
        width: 512,
        height: 512,
        alt: "AusLaw AI logo",
      },
    ],
  },
  twitter: {
    card: "summary",
    title: "AusLaw AI - Australian Legal Assistant",
    description:
      "Get instant answers about Australian law, find qualified lawyers, and receive step-by-step legal guidance.",
    images: ["/icon.png"],
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en-AU">
      <body>
        {/* Connect via Next.js API route to Python backend */}
        <CopilotKit runtimeUrl="/api/copilotkit" agent="auslaw_agent">
          <ModeProvider>{children}</ModeProvider>
        </CopilotKit>
      </body>
    </html>
  );
}
