import { pathToFileURL } from "node:url";
import { resolve } from "node:path";
import { chromium } from "playwright";

const htmlFiles = process.argv.slice(2).length
  ? process.argv.slice(2)
  : ["drive_comparison.html", "drive_comparison_en.html"];

const failures = [];

function expect(condition, message) {
  if (!condition) failures.push(message);
}

async function verifyHtmlFile(browser, htmlFile) {
  const absolutePath = resolve(htmlFile);
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const consoleErrors = [];
  const pageErrors = [];
  page.on("console", message => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", error => pageErrors.push(error.message));

  await page.goto(pathToFileURL(absolutePath).href, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("#chart .data-point", { timeout: 15000 });

  const title = await page.locator("h1").innerText();
  const visiblePoints = await page.locator("#chart .data-point").count();
  const categoryHelpCount = await page.locator(".category-row[data-help]").count();
  const overlayHelpCount = await page.locator("#bandAnalysisControls .check-row[data-help]").count();
  const usageText = await page.locator("#tooltip .usage-panel").innerText();
  const customHelpRuleCount = await page.evaluate(() => {
    return [...document.styleSheets].reduce((count, sheet) => {
      return count + [...sheet.cssRules].filter(rule => String(rule.selectorText || "").includes("[data-help]::after")).length;
    }, 0);
  });

  expect(/Drive Comparison|드라이브 비교/.test(title), `${htmlFile}: title did not render`);
  expect(visiblePoints > 0, `${htmlFile}: no chart data points rendered`);
  expect(categoryHelpCount >= 5, `${htmlFile}: category help tooltips were not attached`);
  expect(overlayHelpCount >= 4, `${htmlFile}: overlay help tooltips were not attached`);
  expect(customHelpRuleCount === 0, `${htmlFile}: custom data-help tooltip rule still exists`);
  expect(/detail cards|상세 카드 사용법/.test(usageText), `${htmlFile}: empty detail panel usage text missing`);

  const firstPoint = page.locator("#chart .data-point").first();
  const pointBox = await firstPoint.boundingBox();
  expect(!!pointBox, `${htmlFile}: first data point has no screen box`);
  if (pointBox) {
    await page.mouse.move(pointBox.x + pointBox.width / 2, pointBox.y + pointBox.height / 2);
  }
  await page.waitForSelector("#tooltip .tooltip-item", { timeout: 10000 });
  const cardCountAfterHover = await page.locator("#tooltip .tooltip-item").count();
  expect(cardCountAfterHover > 0, `${htmlFile}: hover did not create detail card`);

  const firstPin = page.locator("#tooltip .tooltip-item-pin").first();
  await firstPin.click();
  expect(await firstPin.getAttribute("aria-pressed") === "true", `${htmlFile}: card pin did not toggle on`);
  expect(await page.locator("#tooltip .tooltip-item.is-pinned").count() > 0, `${htmlFile}: pinned card styling missing`);

  await page.locator("#thrusters").evaluate(input => {
    input.value = "2";
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await page.waitForTimeout(100);
  const pinnedCountAfterThrusterChange = await page.locator("#tooltip .tooltip-item.is-pinned").count();
  const pinnedTitleAfterThrusterChange = pinnedCountAfterThrusterChange
    ? await page.locator("#tooltip .tooltip-item.is-pinned h2").first().innerText()
    : "";
  expect(pinnedCountAfterThrusterChange > 0, `${htmlFile}: changing engine count removed pinned card`);
  expect(/\bx2\b/.test(pinnedTitleAfterThrusterChange), `${htmlFile}: pinned card did not follow engine count change`);

  await page.locator(".tooltip-close").click();
  expect(await page.locator("#tooltip .tooltip-item.is-pinned").count() > 0, `${htmlFile}: clear-all removed pinned cards`);
  await page.locator("#tooltip .tooltip-item-close").first().click();
  expect(await page.locator("#tooltip .usage-panel").count() > 0, `${htmlFile}: removing final pinned card did not restore usage panel`);

  expect(consoleErrors.length === 0, `${htmlFile}: console errors: ${consoleErrors.join(" | ")}`);
  expect(pageErrors.length === 0, `${htmlFile}: page errors: ${pageErrors.join(" | ")}`);

  await page.close();
}

const browser = await chromium.launch({ headless: true });
try {
  for (const htmlFile of htmlFiles) {
    await verifyHtmlFile(browser, htmlFile);
  }
} finally {
  await browser.close();
}

if (failures.length) {
  console.error(failures.map(message => `- ${message}`).join("\n"));
  process.exit(1);
}

console.log(`Browser verification passed for ${htmlFiles.join(", ")}`);
