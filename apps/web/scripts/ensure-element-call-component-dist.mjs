/*
Copyright 2026 Armin Dashti

SPDX-License-Identifier: AGPL-3.0-only OR LicenseRef-Element-Commercial
Please see LICENSE in the repository root for full details.
 */

import { cpSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const scriptsDir = dirname(fileURLToPath(import.meta.url));
const vendorRoot = resolve(scriptsDir, "../../../element-call-vendor");
const componentRoot = resolve(scriptsDir, "../node_modules/@element-hq/element-call-component");
const distCss = join(componentRoot, "dist", "element-call.css");

if (existsSync(distCss)) {
    process.exit(0);
}

if (!existsSync(join(vendorRoot, "component", "package.json"))) {
    console.error(
        "[element-web] @element-hq/element-call-component has no dist/ and element-call-vendor is missing.\n" +
            "Clone and build Element Call once at the repo root:\n" +
            "  git clone https://github.com/element-hq/element-call.git element-call-vendor\n" +
            "  cd element-call-vendor && git checkout 6438c18b73773904557baa0b359f3ebed1be76e2\n" +
            "  pnpm install --frozen-lockfile && pnpm build:component\n" +
            "Then re-run pnpm build or pnpm start in apps/web.",
    );
    process.exit(1);
}

console.log("[element-web] Building @element-hq/element-call-component from element-call-vendor...");
const build = spawnSync("pnpm", ["build:component"], { cwd: vendorRoot, stdio: "inherit", shell: true });
if (build.status !== 0) {
    process.exit(build.status ?? 1);
}

const srcDist = join(vendorRoot, "component", "dist");
const dstDist = join(componentRoot, "dist");
mkdirSync(dstDist, { recursive: true });
cpSync(srcDist, dstDist, { recursive: true });

if (!existsSync(distCss)) {
    console.error("[element-web] element-call component build finished but dist/element-call.css is still missing.");
    process.exit(1);
}

console.log("[element-web] element-call component dist/ is ready.");
