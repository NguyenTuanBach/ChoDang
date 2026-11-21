// Nhóm 2 — kiểm tra trên Chrome thật (headless): hàng chờ GV hiện mốc đã nộp + nhật ký, và cửa sổ xem
// minh chứng trực tiếp (ảnh, PDF) không cần tải về. Đăng nhập bằng form như người dùng, click thật.
// Dùng: server đang chạy với dữ liệu seed, `npm i` trong tests/ui, rồi `node queue-preview-check.mjs`
// (BASE_URL mặc định http://127.0.0.1:8000; Caddy: BASE_URL=https://localhost). Ảnh chụp ở tests/ui/screens/.
import { mkdirSync } from "node:fs";
import puppeteer from "puppeteer-core";

const BASE = process.env.BASE_URL || "http://127.0.0.1:8000";
const BROWSER = process.env.BROWSER_PATH || "C:/Program Files/Google/Chrome/Application/chrome.exe";
const OUT = new URL("./screens/", import.meta.url).pathname.replace(/^\/([A-Z]:)/, "$1");
mkdirSync(OUT, { recursive: true });

const results = [];
const check = (name, ok, info = "") => { results.push({ name, ok, info }); console.log(`${ok ? "PASS" : "FAIL"}  ${name}${info ? " — " + info : ""}`); };

const browser = await puppeteer.launch({ executablePath: BROWSER, headless: true, args: ["--ignore-certificate-errors"] });

async function openAs(username, viewport = { width: 1366, height: 900 }) {
  const page = await browser.newPage();
  await page.setViewport(viewport);
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  await page.goto(BASE + "/#/", { waitUntil: "networkidle0" });
  await page.evaluate(() => localStorage.clear());
  await page.reload({ waitUntil: "networkidle0" });
  await page.type("#u", username);
  await page.type("#p", "demo123");
  await Promise.all([page.waitForSelector("h1"), page.click("button[type=submit]")]);
  await page.waitForNetworkIdle();
  return { page, errors };
}

const clickByText = (page, selector, text) => page.evaluate((s, t) => {
  const el = [...document.querySelectorAll(s)].find((e) => e.textContent.trim() === t);
  if (!el) return false;
  el.click();
  return true;
}, selector, text);

async function waitPreview(page) {
  await page.waitForSelector(".preview", { timeout: 10_000 });
  await page.waitForFunction(() => !document.querySelector(".preview__msg")?.textContent.includes("Đang tải"), { timeout: 10_000 });
}

// ---------------------------------------------------------------- 1. gv01: hàng chờ + xem ảnh
{
  const { page, errors } = await openAs("gv01");
  // Mặc định "Ưu tiên": đơn gấp nhất (gia hạn cho mốc đã quá hạn) lên đầu, có nhãn lý do
  const firstCard = () => page.$eval("main .card", (c) => c.innerText).catch(() => "");
  const pressed = () => page.$eval(".src__tabs [aria-pressed=true]", (b) => b.textContent).catch(() => "");
  check("mặc định sắp xếp 'Ưu tiên'", (await pressed()) === "Ưu tiên");
  // Không phụ thuộc dữ liệu: thứ tự trên trang phải khớp điểm API (giảm dần) và đơn đầu có nhãn lý do
  const apiScores = await page.evaluate(async () => {
    const r = await fetch("/api/v1/approvals/queue", { headers: { Authorization: "Bearer " + localStorage.getItem("vin15_token") } });
    const q = await r.json();
    return ["internships", "outlines", "milestones", "extensions", "logs"].flatMap((k) => q[k].map((x) => x.priority.score))
      .sort((a, b) => b - a);
  });
  const domScores = await page.$$eval("main .card[data-priority]", (els) => els.map((e) => Number(e.dataset.priority)));
  check("thứ tự hiển thị = điểm ưu tiên giảm dần, khớp API", JSON.stringify(domScores) === JSON.stringify(apiScores),
    `trang ${domScores.join(",")} · API ${apiScores.join(",")}`);
  const top = await firstCard();
  check("đơn đầu hiện nhãn lý do ưu tiên", /Ưu tiên (cao|vừa)|Đã chờ|cảnh báo|quá hạn|còn \d+ ngày/.test(top),
    top.split("\n").slice(1, 5).join(" / "));
  await page.screenshot({ path: OUT + "g2-gv01-queue-priority.png", fullPage: true });
  await clickByText(page, ".src__tabs button", "Chờ lâu nhất");
  check("chuyển sang 'Chờ lâu nhất'", (await pressed()) === "Chờ lâu nhất" && (await page.$(".queue-section")) === null);
  await clickByText(page, ".src__tabs button", "Theo loại");
  await page.reload({ waitUntil: "networkidle0" });
  await page.waitForSelector(".queue-section");
  check("lựa chọn 'Theo loại' được nhớ sau khi tải lại trang", (await pressed()) === "Theo loại");

  const sections = await page.$$eval(".queue-section", (els) => els.map((e) => e.textContent.trim()));
  check("gv01 hàng chờ có nhóm 'Mốc đã nộp'", sections.some((s) => s.startsWith("Mốc đã nộp")), sections.join(" | "));
  check("gv01 hàng chờ có nhóm 'Nhật ký tuần'", sections.some((s) => s.startsWith("Nhật ký tuần")));
  const cards = await page.$$eval("section[aria-label='Mốc đã nộp'] .card", (els) => els.map((e) => e.innerText));
  check("thấy mốc 'Nộp báo cáo giữa kỳ' của sv04", cards.some((t) => t.includes("Nộp báo cáo giữa kỳ")));
  check("mốc thiếu minh chứng có cảnh báo", cards.some((t) => t.includes("Thiếu minh chứng bắt buộc")));
  await page.screenshot({ path: OUT + "g2-gv01-queue.png", fullPage: true });

  check("bấm 'hand_calc.jpg' mở cửa sổ xem", await clickByText(page, ".link-btn", "hand_calc.jpg"));
  await waitPreview(page);
  await page.waitForFunction(() => document.querySelector(".preview__img")?.complete, { timeout: 10_000 }).catch(() => {});
  const img = await page.$eval(".preview__img", (i) => ({ w: i.naturalWidth, h: i.naturalHeight })).catch(() => null);
  check("ảnh hiển thị trong cửa sổ (không tải về)", img && img.w > 0, img ? `${img.w}×${img.h}px` : "không có <img>");
  await page.screenshot({ path: OUT + "g2-gv01-preview-image.png" });
  await page.keyboard.press("Escape");
  check("Esc đóng cửa sổ xem", (await page.$(".preview")) === null);
  check("gv01 không có lỗi JS/console", errors.length === 0, errors.join(" | "));
  await page.close();
}

// ---------------------------------------------------------------- 1b. gv03: thứ tự ưu tiên trên dữ liệu khác
{
  const { page, errors } = await openAs("gv03");
  const scores = await page.$$eval("main .card[data-priority]", (els) => els.map((e) => Number(e.dataset.priority)));
  check("gv03: điểm giảm dần theo thứ tự hiển thị", scores.length > 0 && scores.every((s, k) => k === 0 || scores[k - 1] >= s), scores.join(","));
  const top = await page.$eval("main .card", (c) => c.innerText).catch(() => "");
  check("gv03: đơn đầu có lý do ưu tiên", /Ưu tiên (cao|vừa)/.test(top), top.split("\n").slice(1, 6).join(" / "));
  await page.screenshot({ path: OUT + "g2-gv03-queue-priority.png" });
  check("gv03 không có lỗi JS/console", errors.length === 0, errors.join(" | "));
  await page.close();
}

// ---------------------------------------------------------------- 2. sv04 tải PDF thật qua giao diện → gv01 xem
// PDF 1 trang hợp lệ (cùng cấu trúc seed._demo_pdf). Tên file riêng để dễ nhận/dọn: e2e-<thời điểm>.pdf
function demoPdf(title) {
  const text = `BT /F1 20 Tf 72 760 Td (VIN-15 - kiem thu xem truc tiep) Tj 0 -32 Td /F1 14 Tf (${title}) Tj ET`;
  const objs = [
    "<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>", `<< /Length ${text.length} >>\nstream\n${text}\nendstream`,
  ];
  let out = "%PDF-1.4\n";
  const offsets = objs.map((body, n) => { const at = out.length; out += `${n + 1} 0 obj\n${body}\nendobj\n`; return at; });
  const xref = out.length;
  out += `xref\n0 ${objs.length + 1}\n0000000000 65535 f \n` + offsets.map((o) => `${String(o).padStart(10, "0")} 00000 n \n`).join("");
  return out + `trailer\n<< /Size ${objs.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
}
const pdfName = `e2e-${Date.now()}.pdf`;
{
  const { writeFileSync } = await import("node:fs");
  writeFileSync(OUT + pdfName, demoPdf(pdfName));
  const { page, errors } = await openAs("sv04");
  await page.waitForSelector(".timeline__item");
  const input = await page.evaluateHandle(() => [...document.querySelectorAll(".timeline__item")]
    .find((li) => li.textContent.includes("Nộp báo cáo cuối kỳ"))?.querySelector("input[type=file]"));
  check("sv04 thấy ô tải minh chứng ở mốc 'Nộp báo cáo cuối kỳ'", Boolean(input.asElement()));
  const uploaded = page.waitForResponse((r) => r.url().includes("/evidence") && r.request().method() === "POST");
  await input.asElement().uploadFile(OUT + pdfName);
  check("sv04 tải PDF lên qua giao diện", (await uploaded).status() === 201);
  await page.waitForFunction((n) => document.body.innerText.includes(n), {}, pdfName);
  check("sv04 không có lỗi JS/console", errors.length === 0, errors.join(" | "));
  await page.close();
}
{
  const { page, errors } = await openAs("gv01");
  await clickByText(page, "nav a, aside a", "Sinh viên");  // đi bằng menu như người dùng
  await page.waitForSelector("tbody a[href*='internship']", { timeout: 10_000 });
  check("gv01 mở chi tiết hồ sơ sv04 từ danh sách", await page.evaluate(() => {
    const link = document.querySelector("tbody a[href*='internship']");
    link?.click();
    return Boolean(link);
  }));
  await page.waitForSelector(".timeline .link-btn", { timeout: 10_000 });
  // trình xem PDF giữ kết nối mở → không chờ "network idle", chờ đúng response của file
  const fileResponse = page.waitForResponse((res) => res.url().includes("/api/v1/files/"), { timeout: 10_000 }).catch(() => null);
  check(`bấm '${pdfName}' mở cửa sổ xem`, await clickByText(page, ".link-btn", pdfName));
  await waitPreview(page);
  const frame = await page.$eval(".preview__frame", (f) => f.getAttribute("src")).catch(() => null);
  check("PDF nhúng bằng iframe link inline", Boolean(frame?.includes("inline=1")), frame ? "src có inline=1" : "không có iframe");
  const r = await fileResponse;
  await new Promise((ok) => setTimeout(ok, 1500));  // cho trình xem PDF vẽ trang trước khi chụp
  const h = r?.headers() || {};
  check("file PDF trả 200 + Content-Disposition inline", r?.status() === 200 && (h["content-disposition"] || "").startsWith("inline"),
    `${r?.status()} ${h["content-type"]} ${h["content-disposition"]}`);
  const blocked = page.frames().some((f) => f.url().startsWith("chrome-error://"));
  check("iframe không bị trình duyệt chặn", !blocked);
  await page.screenshot({ path: OUT + "g2-gv01-preview-pdf.png" });
  check("nút 'Đóng' đóng cửa sổ", await clickByText(page, ".preview button", "Đóng") && (await page.$(".preview")) === null);
  check("gv01 (PDF) không có lỗi JS/console", errors.length === 0, errors.join(" | "));
  await page.close();
}

// ---------------------------------------------------------------- 3. PDF hỏng (file demo cũ) → thông báo tiếng Việt
{
  const { page, errors } = await openAs("gv02");
  await clickByText(page, "nav a, aside a", "Sinh viên");
  await page.waitForSelector("tbody a[href*='internship']", { timeout: 10_000 });
  await page.evaluate(() => [...document.querySelectorAll("tbody tr")].find((e) => e.textContent.includes("SV2026005"))
    ?.querySelector("a[href*='internship']")?.click());
  await page.waitForSelector(".timeline .link-btn", { timeout: 10_000 });
  await clickByText(page, ".link-btn", "midterm_report.pdf");
  await waitPreview(page);
  const msg = await page.$eval(".preview__body", (b) => b.innerText);
  const isBroken = msg.includes("bị hỏng");
  const rendered = (await page.$(".preview__frame")) !== null;
  // DB seed mới (sau khi sửa seed): PDF hợp lệ → iframe; DB seed cũ: file 82 byte → thông báo hỏng
  check("PDF demo: hiện iframe (seed mới) hoặc báo 'bị hỏng' bằng tiếng Việt (seed cũ)", isBroken || rendered,
    isBroken ? "seed cũ → thông báo tiếng Việt" : "seed mới → iframe");
  await page.screenshot({ path: OUT + "g2-gv02-preview-broken-pdf.png" });
  check("gv02 không có lỗi JS/console", errors.length === 0, errors.join(" | "));
  await page.close();
}

// ---------------------------------------------------------------- 3b. SV tải PDF hỏng → bị chặn, báo tiếng Việt
{
  const { writeFileSync } = await import("node:fs");
  writeFileSync(OUT + "hong.pdf", "%PDF-1.4\n%khong co trang nao\n%%EOF\n");
  const { page } = await openAs("sv04");
  await page.waitForSelector(".timeline__item");
  const input = await page.evaluateHandle(() => [...document.querySelectorAll(".timeline__item")]
    .find((li) => li.textContent.includes("Nộp báo cáo cuối kỳ"))?.querySelector("input[type=file]"));
  const resp = page.waitForResponse((r) => r.url().includes("/evidence") && r.request().method() === "POST");
  await input.asElement().uploadFile(OUT + "hong.pdf");
  check("upload PDF hỏng bị từ chối (422)", (await resp).status() === 422);
  const toast = await page.waitForSelector(".toast", { timeout: 5_000 }).then((t) => t.evaluate((e) => e.textContent)).catch(() => "");
  check("SV thấy thông báo 'PDF bị hỏng' tiếng Việt", toast.includes("PDF bị hỏng"), toast);
  check("file hỏng không xuất hiện trong danh sách", !(await page.evaluate(() => document.body.innerText.includes("hong.pdf"))));
  await page.close();
}

// ---------------------------------------------------------------- 3c. Nhật ký: nhắc tuần còn thiếu
{
  const { page, errors } = await openAs("sv03");
  await clickByText(page, "nav a, aside a", "Nhật ký");
  await page.waitForSelector("#l-week");
  check("sv03 ghi đủ tuần → không có banner nhắc", !(await page.evaluate(() => document.body.innerText.includes("Bạn chưa ghi nhật ký"))));
  // Không SV nào đang thiếu tuần trong dữ liệu hiện tại → giả lập response để kiểm tra phần hiển thị
  await page.setRequestInterception(true);
  page.on("request", (req) => (req.url().endsWith("/logs/missing")
    ? req.respond({ contentType: "application/json", body: JSON.stringify({ weeks: [3, 4], citation: { doc: "QĐ-TT/2026", path: "Điều 8 / Khoản 1" } }) })
    : req.continue()));
  await page.reload({ waitUntil: "networkidle0" });
  await page.waitForSelector(".alert");
  const alert = await page.$eval(".alert", (a) => a.innerText);
  check("(giả lập thiếu tuần 3, 4) banner nhắc kèm căn cứ", alert.includes("tuần 3, 4") && alert.includes("Điều 8 / Khoản 1"), alert.replace(/\n/g, " / "));
  check("ô 'Tuần' điền sẵn tuần thiếu sớm nhất", (await page.$eval("#l-week", (i) => i.value)) === "3");
  await page.screenshot({ path: OUT + "g2-sv03-logs-reminder.png" });
  check("trang nhật ký không có lỗi JS/console", errors.length === 0, errors.join(" | "));
  await page.close();
}

// ---------------------------------------------------------------- 3d. AI hỗ trợ đọc minh chứng
// sv04 nộp báo cáo Word qua giao diện → gv01 mở xem: panel "Gợi ý AI" có tóm tắt + checklist + giới hạn.
{
  const fixture = new URL("./fixtures/bao-cao-cuoi-ky-mau.docx", import.meta.url).pathname.replace(/^\/([A-Z]:)/, "$1");
  const sv = await openAs("sv04");
  await sv.page.waitForSelector(".timeline__item");
  const input = await sv.page.evaluateHandle(() => [...document.querySelectorAll(".timeline__item")]
    .find((li) => li.textContent.includes("Nộp báo cáo cuối kỳ"))?.querySelector("input[type=file]"));
  const up = sv.page.waitForResponse((r) => r.url().includes("/evidence") && r.request().method() === "POST");
  await input.asElement().uploadFile(fixture);
  check("sv04 nộp báo cáo Word qua giao diện", (await up).status() === 201);
  await sv.page.waitForFunction(() => document.body.innerText.includes("bao-cao-cuoi-ky-mau.docx"));
  await clickByText(sv.page, ".link-btn", "bao-cao-cuoi-ky-mau.docx");
  await waitPreview(sv.page);
  check("SV mở file của mình: KHÔNG có panel gợi ý AI", (await sv.page.$(".preview__ai")) === null);
  await sv.page.close();

  const { page, errors } = await openAs("gv01");
  await clickByText(page, "nav a, aside a", "Sinh viên");
  await page.waitForSelector("tbody a[href*='internship']");
  await page.evaluate(() => document.querySelector("tbody a[href*='internship']").click());
  await page.waitForSelector(".timeline .link-btn");
  await clickByText(page, ".link-btn", "bao-cao-cuoi-ky-mau.docx");
  await waitPreview(page);
  check("GV mở báo cáo Word: thấy nội dung chữ", (await page.$eval(".preview__body", (b) => b.innerText)).includes("Tự đánh giá"));
  const ai = await page.waitForSelector(".preview__ai .ai-box", { timeout: 45_000 }).then((b) => b.evaluate((e) => e.innerText)).catch(() => "");
  check("panel 'Gợi ý AI' có nhãn GV quyết định", ai.includes("GV là người quyết định"));
  check("checklist báo cáo cuối kỳ hiển thị", ai.includes("Checklist: Báo cáo cuối kỳ") && ai.includes("Tự đánh giá"));
  const items = await page.$$eval(".ai-checklist li", (els) => els.map((e) => `${e.className}:${e.textContent.trim()}`));
  check("'Bài học kinh nghiệm' (file không có) được đánh '?'", items.some((t) => t.startsWith("is-missing") && t.includes("Bài học")), items.join(" | "));
  check("ghi rõ AI không xác nhận chữ ký/con dấu", ai.includes("không xác nhận được chữ ký"));
  await page.screenshot({ path: OUT + "g2-gv01-ai-review-docx.png" });
  await page.keyboard.press("Escape");

  // Ảnh "phiếu đánh giá" thật ra là ảnh chụp bài tính tay → AI phải cảnh báo
  await clickByText(page, ".link-btn", "hand_calc.jpg");
  await waitPreview(page);
  const aiImg = await page.waitForSelector(".preview__ai .ai-box, .preview__ai .muted:not(:empty)", { timeout: 90_000 })
    .then(() => page.$eval(".preview__ai", (a) => a.innerText)).catch(() => "");
  const warned = await page.$$eval(".ai-warnings li", (els) => els.map((e) => e.textContent));
  check("ảnh không phải phiếu đánh giá → có cảnh báo", warned.length > 0, warned.join(" | ") || aiImg.slice(0, 200));
  await page.screenshot({ path: OUT + "g2-gv01-ai-review-image.png" });
  check("AI review không có lỗi JS/console", errors.length === 0, errors.join(" | "));
  await page.close();
}

// ---------------------------------------------------------------- 4. điện thoại 390px
{
  const { page, errors } = await openAs("gv01", { width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  check("390px: hàng chờ không tràn ngang", overflow <= 0, `${overflow}px`);
  await page.screenshot({ path: OUT + "g2-mobile-queue.png", fullPage: true });
  await clickByText(page, ".link-btn", "hand_calc.jpg");
  await waitPreview(page);
  const box = await page.$eval(".preview", (p) => p.getBoundingClientRect().toJSON());
  check("390px: cửa sổ xem chiếm toàn màn hình", Math.round(box.width) === 390, `${Math.round(box.width)}×${Math.round(box.height)}`);
  await page.screenshot({ path: OUT + "g2-mobile-preview.png" });
  check("mobile không có lỗi JS/console", errors.length === 0, errors.join(" | "));
  await page.close();
}

await browser.close();
const failed = results.filter((r) => !r.ok).length;
console.log(`\n${results.length - failed}/${results.length} PASS — ảnh chụp: ${OUT}`);
process.exit(failed ? 1 : 0);
