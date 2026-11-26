import type { Metadata } from "next";
import { Inter } from "next/font/google";
import type { ReactNode } from "react";

import { AuthProvider } from "@/components/AuthProvider";

import "./globals.css";

const inter = Inter({
  subsets: ["latin", "vietnamese"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "Chatbot RAG luyện thi AWS SAA-C03",
    template: "%s | AWS SAA-C03",
  },
  description:
    "Chatbot hỗ trợ tự học và luyện thi chứng chỉ AWS Certified Solutions Architect – Associate (SAA-C03).",
  icons: {
    icon: "/favicon.ico",
  },
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="vi" className={inter.variable}>
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
