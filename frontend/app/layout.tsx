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
    // suppressHydrationWarning: Dark Reader 等のブラウザ拡張が React 読込前に
    // <html> へ属性を注入して起きる hydration 警告を抑制する（この要素の属性のみ対象）
    <html lang="ja" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
