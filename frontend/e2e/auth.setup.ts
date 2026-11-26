import { readFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";

import { expect, test as setup } from "@playwright/test";

const STATE_PATH = resolve(__dirname, ".auth", "state.json");
const CREDENTIALS_PATH = resolve(__dirname, ".auth", "credentials.json");

setup("đăng nhập bằng tài khoản thử nghiệm", async ({ page }) => {
  const credentials = JSON.parse(readFileSync(CREDENTIALS_PATH, "utf8")) as {
    email: string;
    password: string;
  };

  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "Đăng nhập để tiếp tục" })).toBeVisible();
  await page.getByLabel("Email").fill(credentials.email);
  await page.locator('input[name="password"]').fill(credentials.password);
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();

  await expect(page).toHaveURL(/\/chat/, { timeout: 30_000 });
  await expect(page.getByRole("heading", { name: "Hỏi đáp tài liệu" })).toBeVisible();
  await expect(page.getByText("Đã đăng nhập").first()).toBeVisible({ timeout: 30_000 });

  mkdirSync(dirname(STATE_PATH), { recursive: true });
  await page.context().storageState({ path: STATE_PATH });
});
