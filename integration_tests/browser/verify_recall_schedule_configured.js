async page => {
  const checks = [];
  const check = (condition, message) => {
    if (!condition) throw new Error(message);
    checks.push(message);
  };
  const origin = new URL(page.url()).origin;
  const api = async (path, init = {}) => {
    const token = await page.evaluate(() => localStorage.getItem("runestone_token"));
    const response = await page.request.fetch(`${origin}${path}`, {
      ...init,
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        ...(init.headers ?? {}),
      },
    });
    return response;
  };
  const selectedHour = async role => {
    const text = await page.getByRole("combobox", { name: role }).textContent();
    return Number.parseInt(text ?? "", 10);
  };
  const chooseHour = async (role, hour) => {
    const combo = page.getByRole("combobox", { name: role });
    await combo.focus();
    await combo.press("Enter");
    await combo.press("Home");
    for (let index = 0; index < hour; index += 1) {
      await combo.press("ArrowDown");
    }
    await combo.press("Enter");
  };

  await page.goto(`${origin}/?view=recall`);
  await page.getByRole("heading", { name: "Delivery schedule" }).waitFor();
  const initial = await (await api("/api/recall")).json();
  const initialProfile = await (await api("/api/me")).json();
  check(initial.configured === true, "configured account is linked");

  // Profile timezone selection is selection-only and persists after reload.
  try {
    await page.goto(`${origin}/?view=profile`);
    const timezone = page.getByLabel("Timezone");
    await timezone.focus();
    await timezone.press("ControlOrMeta+A");
    await timezone.type("America/New_York");
    await timezone.press("ArrowDown");
    await timezone.press("Enter");
    const updateProfile = page.getByRole("button", { name: "Update Profile" });
    await updateProfile.focus();
    await updateProfile.press("Enter");
    await page.getByText("Profile updated successfully!").waitFor();
    await page.reload();
    check((await page.getByLabel("Timezone").inputValue()) === "America/New_York", "selected timezone survives reload");
  } finally {
    await api("/api/me", {
      method: "PUT",
      data: { timezone: initialProfile.timezone },
    });
  }
  await page.goto(`${origin}/?view=recall`);
  await page.getByRole("heading", { name: "Delivery schedule" }).waitFor();

  const starts = page.getByRole("combobox", { name: "Starts" });
  const ends = page.getByRole("combobox", { name: "Ends" });
  check(await starts.isEnabled(), "start selector is enabled");
  check(await ends.isEnabled(), "end selector is enabled");
  check(await page.getByRole("button", { name: "Stop delivery" }).isEnabled(), "stop control is enabled");

  const patchRequests = [];
  const requestListener = request => {
    if (request.method() === "PATCH" && request.url().endsWith("/api/recall/settings")) {
      patchRequests.push(request.postDataJSON());
    }
  };
  page.on("request", requestListener);
  try {
    // Keyboard-only schedule editing and the equal-hour validation path.
    await chooseHour("Starts", 1);
    await chooseHour("Ends", 1);
    await page.getByRole("button", { name: "Save times" }).waitFor();
    check(await page.getByRole("button", { name: "Save times" }).isDisabled(), "equal hours disable save");
    check(await page.getByRole("alert").filter({ hasText: "must be different" }).isVisible(), "equal hours expose an error");
    check(patchRequests.length === 0, "equal hours do not send a patch");

    // Make a valid dirty draft and verify Stop atomically carries both hours.
    await chooseHour("Starts", 1);
    await chooseHour("Ends", 23);
    const stop = page.getByRole("button", { name: "Stop delivery" });
    await stop.focus();
    await stop.press("Enter");
    await page.waitForResponse(response => response.url().endsWith("/api/recall/settings") && response.request().method() === "PATCH");
    const stopPayload = patchRequests.at(-1);
    check(stopPayload?.delivery_enabled === false, "stop sends delivery_enabled false");
    check(Number.isInteger(stopPayload?.recall_start_hour) && Number.isInteger(stopPayload?.recall_end_hour), "stop sends both draft hours");

    // A failed Save keeps the draft visible and leaves the authoritative status alone.
    await page.route("**/api/recall/settings", route =>
      route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: "settings unavailable" }) })
    );
    await chooseHour("Starts", 2);
    const failedStart = await selectedHour("Starts");
    const save = page.getByRole("button", { name: "Save times" });
    await save.focus();
    await save.press("Enter");
    await page.getByRole("alert").filter({ hasText: "settings unavailable" }).waitFor();
    check((await selectedHour("Starts")) === failedStart, "failed save retains the draft");
  } finally {
    await page.unroute("**/api/recall/settings");
    // Restore the fixture account through the same authenticated API boundary.
    await api("/api/recall/settings", {
      method: "PATCH",
      data: {
        recall_start_hour: initial.recall_start_hour,
        recall_end_hour: initial.recall_end_hour,
        delivery_enabled: initial.delivery_enabled,
      },
    });
    page.off("request", requestListener);
  }

  const evidenceDir = typeof process !== "undefined" && process.env.BROWSER_EVIDENCE_DIR
    ? process.env.BROWSER_EVIDENCE_DIR
    : undefined;
  if (evidenceDir) {
    await page.reload();
    await page.getByRole("heading", { name: "Delivery schedule" }).waitFor();
    await page.screenshot({ path: `${evidenceDir}/recall-schedule-configured.png`, fullPage: true });
    try {
      const fs = await import("node:fs/promises");
      await fs.writeFile(`${evidenceDir}/recall-schedule-configured.json`, JSON.stringify({ ok: true, checks }, null, 2));
    } catch {
      // The CLI may evaluate in a browser-only context; returned checks remain the evidence.
    }
  }
  return { ok: true, checks };
}
