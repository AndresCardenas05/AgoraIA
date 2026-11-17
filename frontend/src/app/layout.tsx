import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ÁgoraIA — Ética Periodística, Comunicación Digital e IA",
  description:
    "Chatbot analítico RAG para consultar normativa argentina y analizar dilemas éticos sobre periodismo e Inteligencia Artificial generativa.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es">
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
