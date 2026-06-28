import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "image-movie",
  description: "画像から BGM 付きスライドショー動画を生成します",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ja">
      <body>{children}</body>
    </html>
  );
}
