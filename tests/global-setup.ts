/**
 * Global setup is a no-op — user seeding is done in playwright.config.ts
 * at module load time, before webServer starts.
 * (Playwright starts webServer BEFORE globalSetup, so we can't seed here.)
 */
async function globalSetup() {
  // No-op
}

export default globalSetup;
