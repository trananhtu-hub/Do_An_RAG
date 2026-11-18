import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "Chatbot RAG luyện thi AWS SAA-C03",
  description:
    "Chatbot hỗ trợ tự học và luyện thi chứng chỉ AWS Certified Solutions Architect – Associate (SAA-C03).",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="vi">
      <body>{children}</body>
    </html>
  );
}
