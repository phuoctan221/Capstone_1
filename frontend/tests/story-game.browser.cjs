// Run with PLAYWRIGHT_MODULE pointing to an installed playwright module if not local.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const os = require("node:os");

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  const user = { id: "browser-test", username: "Người học", role: "user", onboarded: true };
  const vocabulary = ["journey", "ticket", "discover", "village", "friendly", "share", "memory", "invoice"].map((word, i) => ({ id: String(i), word, meaning: i === 0 ? "chuyến hành trình" : "Nghĩa của từ" }));
  let failGeneration = true;
  let saved = null;
  const story = {
    id: "507f1f77bcf86cd799439011", title: "The Ticket to Somewhere New", topic: "travel", tone: "warm", source: "ai", words: vocabulary.slice(0, 7),
    paragraphs: ["Linh bought a ticket for a journey to a quiet village. She wanted to discover something new. A friendly baker welcomed her into the shop.", "They decided to share bread by the river. Linh drew a picture as a memory of her day. She promised to visit the village again."],
    translation: ["Linh mua vé đi tới một ngôi làng yên tĩnh.", "Họ chia sẻ bánh mì bên dòng sông."],
    questions: [
      { question: "Where did Linh go?", options: ["A village", "An office", "A school", "A beach"] },
      { question: "Who welcomed her?", options: ["A driver", "A baker", "A teacher", "A doctor"] },
      { question: "What did they share?", options: ["Books", "Tickets", "Bread", "Money"] },
    ], created_at: "2026-11-16T08:00:00Z", result: null,
  };
  await page.addInitScript(user => { localStorage.setItem("token", "browser-test-token"); localStorage.setItem("user", JSON.stringify(user)); }, user);
  await page.route("**/api/**", async route => {
    const url = new URL(route.request().url());
    const send = (data, status = 200) => route.fulfill({ status, json: data });
    if (url.pathname === "/api/auth/me") return send(user);
    if (url.pathname.endsWith("/games/story/words")) return send(vocabulary);
    if (url.pathname.endsWith("/answers")) {
      assert.deepEqual(route.request().postDataJSON().answers, [0, 1, 2]);
      saved.result = { score: 3, total: 3, feedback: [0, 1, 2].map(answer => ({ correct: true, answer, selected: answer, explanation: "Thông tin có trong câu chuyện." })) };
      return send(saved.result);
    }
    if (url.pathname.endsWith("/stories") && route.request().method() === "POST") {
      const input = route.request().postDataJSON();
      assert.equal(input.vocabulary_ids.length, 7);
      if (failGeneration) return send({ detail: "Chưa tạo được truyện lúc này. Bạn thử lại hoặc chơi truyện mẫu trước nhé." }, 503);
      saved = structuredClone(story); return send(saved, 201);
    }
    if (url.pathname.endsWith("/demo")) { saved = { ...structuredClone(story), source: "demo" }; return send(saved, 201); }
    if (url.pathname.endsWith("/stories")) return send(saved ? [{ ...saved, score: saved.result?.score ?? null }] : []);
    if (url.pathname.endsWith(story.id)) return send(saved);
    return send({});
  });
  const output = process.env.STORY_SCREENSHOTS || path.join(os.tmpdir(), "capstone-story-preview");
  fs.mkdirSync(output, { recursive: true });
  try {
    await page.goto("http://localhost:5173/games/story");
    await page.getByRole("heading", { name: "Mỗi từ mở ra một câu chuyện" }).waitFor();
    await page.screenshot({ path: path.join(output, "empty-desktop.png"), fullPage: true });
    assert(await page.getByRole("button", { name: "Tạo truyện mới", exact: true }).isDisabled());
    await page.getByRole("button", { name: "+ Chọn từ đã học", exact: true }).click();
    await page.getByLabel("Tìm từ hoặc nghĩa tiếng Việt").fill("hanh trinh");
    assert.equal(await page.locator(".story-word-options label").count(), 1);
    await page.getByLabel("Tìm từ hoặc nghĩa tiếng Việt").fill("");
    for (let i = 0; i < 7; i++) await page.locator('.story-word-options input').nth(i).check();
    assert(await page.locator('.story-word-options input').nth(7).isDisabled());
    await page.getByRole("button", { name: "Tạo truyện mới", exact: true }).click();
    await page.getByRole("alert").filter({ hasText: "Chưa tạo được truyện" }).waitFor();
    failGeneration = false;
    await page.getByRole("button", { name: "Tạo truyện mới", exact: true }).click();
    await page.getByRole("heading", { name: story.title }).waitFor();
    assert.equal(await page.locator(".story-explanation").count(), 0);
    await page.locator(".story-inline-word").first().click();
    await page.locator(".story-word-meaning").waitFor();
    await page.getByRole("button", { name: "Xem bản dịch tiếng Việt" }).click();
    await page.locator("#story-translation").waitFor();
    for (let i = 0; i < 3; i++) await page.locator(".story-quiz fieldset").nth(i).getByRole("radio").nth(i).check();
    await page.getByRole("button", { name: "Kiểm tra đáp án", exact: true }).click();
    await page.locator(".story-score").filter({ hasText: "3/3" }).waitFor();
    await page.screenshot({ path: path.join(output, "story-desktop.png"), fullPage: true });
    await page.getByRole("button", { name: "Lịch sử truyện", exact: true }).click();
    await page.locator(".story-history li button").click();
    await page.locator(".story-score").filter({ hasText: "3/3" }).waitFor();
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({ path: path.join(output, "story-mobile.png"), fullPage: true });
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.getByRole("button", { name: "Tạo câu chuyện tiếp theo" }).click();
    await page.getByRole("button", { name: "Chơi thử với truyện mẫu" }).click();
    await page.locator(".story-reader-meta").filter({ hasText: "Truyện mẫu" }).waitFor();
    assert.deepEqual(errors, []);
    console.log("Browser checks passed: selection/search/limit, generation error and recovery, glossary, translation, quiz, history, mobile, demo.");
    console.log("Screenshots:", output);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
