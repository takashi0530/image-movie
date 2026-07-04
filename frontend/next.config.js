/** @type {import('next').NextConfig} */
const nextConfig = {
  // 静的エクスポート（next build → out/）。本番は FastAPI が out/ を同一オリジンで配信する。
  // 開発は従来どおり next dev を使う（output は build にのみ影響）。
  output: "export",
};

module.exports = nextConfig;
