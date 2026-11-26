import { expect, test } from "@playwright/test";

const QUESTION = "So sánh Multi-AZ và Read Replica cho cơ sở dữ liệu RDS.";

test.describe.configure({ mode: "serial" });

test.describe("Luồng MVP Giai đoạn 5", () => {
  test("hỏi đáp: nhận câu trả lời trực tiếp và mở trích dẫn PDF", async ({ page }) => {
    const metaLoaded = page.waitForResponse(
      (response) =>
        response.request().method() === "GET" &&
        new URL(response.url()).pathname === "/meta",
    );
    await page.goto("/chat");
    await expect(page.getByRole("heading", { name: "Hỏi đáp tài liệu" })).toBeVisible();
    await metaLoaded;

    const composer = page.getByLabel("Câu hỏi của bạn");
    await composer.fill(QUESTION);
    await expect(composer).toHaveValue(QUESTION);
    const sendButton = page.getByRole("button", { name: "Gửi câu hỏi" });
    await expect(sendButton).toBeEnabled({ timeout: 15_000 });
    await sendButton.click();

    await expect(
      page.getByRole("button", { name: "Dừng tạo câu trả lời" }).first(),
    ).toBeVisible({ timeout: 30_000 });

    await expect(page.getByText("Nguồn trích dẫn").first()).toBeVisible({ timeout: 180_000 });
    await expect(page.getByRole("button", { name: "Dừng tạo câu trả lời" })).toHaveCount(0, {
      timeout: 180_000,
    });

    await page.getByTitle("Mở tài liệu gốc tại trang trích dẫn").first().click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    const quoteText = (await dialog.locator("blockquote").innerText().catch(() => "")).trim();
    const fallbackVisible = await dialog
      .getByText("chưa kèm đoạn trích nguyên văn")
      .isVisible()
      .catch(() => false);
    expect(quoteText.length > 0 || fallbackVisible).toBe(true);
    await expect(dialog.locator("iframe")).toBeVisible({ timeout: 120_000 });
    await dialog.getByRole("button", { name: "Đóng hộp thoại" }).click();
    await expect(dialog).not.toBeVisible();
  });

  test("luyện đề: làm 5 câu, nhận kết quả và lưu lịch sử", async ({ page }) => {
    const domainsLoaded = page.waitForResponse(
      (response) =>
        response.request().method() === "GET" && response.url().includes("/quiz/domains"),
    );
    await page.goto("/quiz");
    await expect(page.getByRole("heading", { name: "Luyện đề" })).toBeVisible();
    await domainsLoaded;
    await expect(page.getByText(/Kho hiện có/)).toBeVisible({ timeout: 30_000 });

    await page.getByLabel("Số câu").selectOption("5");
    const startButton = page.getByRole("button", { name: "Bắt đầu làm bài" });
    await expect(startButton).toBeEnabled({ timeout: 30_000 });

    const attemptRows = page.locator("table tbody tr");
    const initialRows = await attemptRows.count();
    const initialFirst = initialRows > 0 ? await attemptRows.first().innerText() : "";

    await startButton.click();
    await expect(page.getByText(/Đã trả lời 0\/5/)).toBeVisible({ timeout: 30_000 });

    const questions = page.locator("ol > li");
    await expect(questions).toHaveCount(5);
    for (let index = 0; index < 5; index += 1) {
      await questions.nth(index).locator('input[type="radio"]').first().check();
    }
    await expect(page.getByText(/Đã trả lời 5\/5/)).toBeVisible();

    await page.getByRole("button", { name: "Nộp bài và xem đáp án" }).click();
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "Nộp bài", exact: true })
      .click();

    await expect(page.getByText(/\d\/5 câu đúng/)).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText("Giải thích").first()).toBeVisible();

    await expect
      .poll(
        async () => {
          const count = await attemptRows.count();
          if (count > initialRows) {
            return true;
          }
          if (count === 0) {
            return false;
          }
          return (await attemptRows.first().innerText()) !== initialFirst;
        },
        { timeout: 30_000 },
      )
      .toBe(true);
  });

  test("lịch sử: tìm, đổi tên và xóa cuộc trò chuyện vừa tạo", async ({ page }) => {
    const sessionsLoaded = page.waitForResponse(
      (response) =>
        response.request().method() === "GET" && response.url().includes("/sessions?limit=100"),
    );
    await page.goto("/history");
    await expect(page.getByRole("heading", { name: "Lịch sử hội thoại" })).toBeVisible();
    await sessionsLoaded;

    await page
      .getByRole("searchbox", { name: "Tìm theo tiêu đề cuộc trò chuyện" })
      .fill("Multi-AZ");

    const row = page.locator("main ul li").filter({ hasText: "Multi-AZ" }).first();
    await expect(row).toBeVisible({ timeout: 30_000 });

    const href = await row.getByRole("link", { name: "Mở" }).getAttribute("href");
    expect(href).toBeTruthy();

    await row.getByRole("button", { name: "Đổi tên" }).click();
    const renameDialog = page.getByRole("dialog");
    await expect(renameDialog).toBeVisible();
    await renameDialog.getByLabel("Tiêu đề mới").fill("Multi-AZ đã đổi tên");
    await renameDialog.getByRole("button", { name: "Lưu tên mới" }).click();
    await expect(page.getByText("Đã đổi tên cuộc trò chuyện.")).toBeVisible();
    await expect(page.getByText("Multi-AZ đã đổi tên")).toBeVisible();

    await row.getByRole("button", { name: "Xóa" }).click();
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "Xóa vĩnh viễn" })
      .click();

    await expect(page.getByText("Đã xóa cuộc trò chuyện.")).toBeVisible();
    await expect(page.locator(`a[href="${href}"]`)).toHaveCount(0);
  });

  test("quản trị: tài khoản học viên không vào được trang quản trị", async ({ page }) => {
    await page.goto("/admin");
    await expect(page.getByText("Không có quyền truy cập")).toBeVisible({ timeout: 30_000 });
  });
});
