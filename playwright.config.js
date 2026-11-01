import {defineConfig, devices} from "@playwright/test";

const port = process.env.CRDR_E2E_PORT || "4173";
const baseURL = `http://127.0.0.1:${port}`;

export default defineConfig({
    testDir: "./tests-e2e",
    fullyParallel: true,
    forbidOnly: Boolean(process.env.CI),
    retries: process.env.CI ? 2 : 0,
    reporter: process.env.CI ? "github" : "list",
    use: {baseURL, screenshot: "only-on-failure", trace: "retain-on-failure"},
    projects: [
        {name: "desktop-chromium", use: {...devices["Desktop Chrome"]}},
        {name: "mobile-chromium", use: {...devices["Pixel 7"]}},
    ],
    webServer: {command: "node scripts/static-server.js", url: baseURL, env:{PORT:port}, reuseExistingServer: !process.env.CI},
});
