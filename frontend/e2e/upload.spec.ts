import { test, expect } from "@playwright/test";
import path from "path";

const FIXTURES = ["a.png", "b.png", "c.png"].map((f) =>
  path.join(__dirname, "fixtures", f),
);

test("画像をアップロードすると動画が生成されプレビュー＆ダウンロードできる", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "image-movie" })).toBeVisible();

  // 画像を選択 → プレビューのサムネイルが3枚出る
  await page.setInputFiles("#images", FIXTURES);
  await expect(page.locator(".preview img")).toHaveCount(3);

  // BGM の選択肢が読み込まれ、1曲選べる
  await expect(page.locator(".track")).not.toHaveCount(0);
  await page.getByRole("radio", { name: "あかるい" }).check();

  // 回転を指定して送信
  await page.selectOption("#rotation", "90");
  await page.getByRole("button", { name: /動画を作成/ }).click();

  // 生成完了を待つ（バックグラウンド生成 + ポーリング）
  const video = page.locator(".result video");
  await expect(video).toBeVisible({ timeout: 60_000 });

  // 動画の src が download エンドポイントを指していること
  const src = await video.getAttribute("src");
  expect(src).toBeTruthy();
  expect(src).toMatch(/\/videos\/.+\/download$/);

  // ダウンロードボタンが表示されること
  await expect(
    page.getByRole("button", { name: "動画をダウンロード" }),
  ).toBeVisible();

  // src が実際に video/mp4 を返すこと
  const resp = await page.request.get(src!);
  expect(resp.status()).toBe(200);
  expect(resp.headers()["content-type"]).toBe("video/mp4");
  const body = await resp.body();
  expect(body.length).toBeGreaterThan(10_000);
});

test("非対応の拡張子はエラー表示される", async ({ page }) => {
  await page.goto("/");
  // gif を渡す（バックエンドが 400 を返す）
  await page.setInputFiles("#images", {
    name: "bad.gif",
    mimeType: "image/gif",
    buffer: Buffer.from("GIF89a"),
  });
  await page.getByRole("button", { name: /動画を作成/ }).click();
  await expect(page.locator(".error")).toBeVisible({ timeout: 15_000 });
});
