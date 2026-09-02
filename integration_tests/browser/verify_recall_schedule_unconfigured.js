async page => {
  const checks = [];
  const check = (condition, message) => {
    if (!condition) throw new Error(message);
    checks.push(message);
  };
  const origin = new URL(page.url()).origin;

  await page.goto(`${origin}/?view=recall`);
  await page.getByRole("heading", { name: "Delivery schedule" }).waitFor();
  check(await page.getByText("Recall is not configured").isVisible(), "onboarding remains visible");
  check(await page.getByRole("combobox", { name: "Starts" }).getAttribute("aria-disabled") === "true", "start selector is disabled");
  check(await page.getByRole("combobox", { name: "Ends" }).getAttribute("aria-disabled") === "true", "end selector is disabled");
  check(await page.getByRole("button", { name: "Start delivery" }).isDisabled(), "start control is disabled");
  check(await page.getByRole("button", { name: "Refresh selection" }).isDisabled(), "queue refresh is disabled");

  const queueActions = page.getByRole("button", { name: /Postpone|Remove|Edit/ });
  const queueActionCount = await queueActions.count();
  for (let index = 0; index < queueActionCount; index += 1) {
    check(await queueActions.nth(index).isDisabled(), "unconfigured queue action is disabled");
  }
  check(true, "unconfigured queue actions are unavailable");
  const evidenceDir = typeof process !== "undefined" && process.env.BROWSER_EVIDENCE_DIR
    ? process.env.BROWSER_EVIDENCE_DIR
    : undefined;
  if (evidenceDir) {
    await page.screenshot({ path: `${evidenceDir}/recall-schedule-unconfigured.png`, fullPage: true });
    try {
      const fs = await import("node:fs/promises");
      await fs.writeFile(`${evidenceDir}/recall-schedule-unconfigured.json`, JSON.stringify({ ok: true, checks }, null, 2));
    } catch {
      // The CLI may evaluate in a browser-only context; returned checks remain the evidence.
    }
  }
  return { ok: true, checks };
}
