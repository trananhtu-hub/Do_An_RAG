import { expect, test } from "@playwright/test";

const CORS_HEADERS = {
  "access-control-allow-origin": "http://localhost:3000",
  "access-control-allow-methods": "POST, OPTIONS",
  "access-control-allow-headers": "authorization, content-type, cache-control, accept",
};

const SESSION_ID = "11111111-1111-4111-8111-111111111111";
const MESSAGE_ID = "22222222-2222-4222-8222-222222222222";

const STREAM_BODY = [
  `event: meta\ndata: ${JSON.stringify({
    session_id: SESSION_ID,
    user_message_id: null,
    message_id: MESSAGE_ID,
    question: "Kiểm thử an toàn Markdown",
    rewritten_query: "Kiểm thử an toàn Markdown",
    rewrite_source: "none",
    depends_on_context: false,
    conversation_tokens: 0,
    conversation_messages: 0,
    summary_used: false,
    replayed: false,
    prepare_ms: 1,
  })}\n\n`,
  `event: token\ndata: ${JSON.stringify({ text: "Xin chào. " })}\n\n`,
  `event: token\ndata: ${JSON.stringify({
    text: '<script>window.__xss=1</script>\n\n',
  })}\n\n`,
  `event: token\ndata: ${JSON.stringify({
    text: '<img src=x onerror="window.__xss=2">\n\n',
  })}\n\n`,
  `event: token\ndata: ${JSON.stringify({
    text: "[bấm](javascript:window.__xss=3)\n\n",
  })}\n\n`,
  `event: token\ndata: ${JSON.stringify({ text: "**đậm**" })}\n\n`,
  `event: citations\ndata: ${JSON.stringify({
    items: [],
    citation_validity: 1,
    unmatched: [],
    warnings: [],
  })}\n\n`,
  `event: done\ndata: ${JSON.stringify({
    session_id: SESSION_ID,
    message_id: MESSAGE_ID,
    status: "complete",
    latency_ms: 1,
    confidence: 1,
  })}\n\n`,
].join("");

test("Markdown chứa thẻ script và liên kết nguy hiểm không được thực thi", async ({ page }) => {
  await page.route("**/chat/stream", async (route) => {
    if (route.request().method() === "OPTIONS") {
      await route.fulfill({ status: 204, headers: CORS_HEADERS });
      return;
    }
    await route.fulfill({
      status: 200,
      headers: { ...CORS_HEADERS, "content-type": "text/event-stream" },
      body: STREAM_BODY,
    });
  });

  const metaLoaded = page.waitForResponse(
    (response) =>
      response.request().method() === "GET" && new URL(response.url()).pathname === "/meta",
  );
  await page.goto("/chat");
  await expect(page.getByRole("heading", { name: "Hỏi đáp tài liệu" })).toBeVisible();
  await metaLoaded;
  await page.getByRole("button", { name: /S3 Glacier Deep Archive/ }).click();

  await expect(page.locator(".markdown").getByText("Xin chào.").first()).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.getByRole("button", { name: "Dừng tạo câu trả lời" })).toHaveCount(0, {
    timeout: 30_000,
  });

  const result = await page.evaluate(() => ({
    executed: (window as unknown as { __xss?: number }).__xss ?? null,
    scriptNodes: Array.from(document.querySelectorAll("script")).filter((node) =>
      node.textContent?.includes("__xss"),
    ).length,
    brokenImages: document.querySelectorAll('img[src="x"]').length,
    unsafeLinks: Array.from(document.querySelectorAll("a")).filter((anchor) =>
      (anchor.getAttribute("href") ?? "").toLowerCase().startsWith("javascript:"),
    ).length,
    boldRendered: document.querySelectorAll(".markdown strong").length > 0,
  }));

  expect(result.executed).toBeNull();
  expect(result.scriptNodes).toBe(0);
  expect(result.brokenImages).toBe(0);
  expect(result.unsafeLinks).toBe(0);
  expect(result.boldRendered).toBe(true);
});
