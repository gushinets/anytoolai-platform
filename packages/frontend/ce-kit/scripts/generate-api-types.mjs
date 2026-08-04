#!/usr/bin/env node
// Wraps openapi-typescript: regenerates src/api/generated/platformApi.ts from the backend's
// committed docs/generated/openapi.json, or (with --check) verifies the committed file is
// still current without touching it.
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const PACKAGE_ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const REPO_ROOT = join(PACKAGE_ROOT, "..", "..", "..");
const SCHEMA_PATH = join(REPO_ROOT, "docs", "generated", "openapi.json");
const OUTPUT_PATH = join(PACKAGE_ROOT, "src", "api", "generated", "platformApi.ts");
const OPENAPI_TS_BIN = join(PACKAGE_ROOT, "node_modules", ".bin", "openapi-typescript");

function generate(outputPath) {
  if (!existsSync(SCHEMA_PATH)) {
    console.error(
      `[APITYPES001] ${SCHEMA_PATH} does not exist. ` +
        "Run: python scripts/agent/runner.py generate-docs",
    );
    process.exit(1);
  }
  execFileSync(OPENAPI_TS_BIN, [SCHEMA_PATH, "-o", outputPath], { stdio: "inherit" });
}

function main() {
  const check = process.argv.includes("--check");

  if (!check) {
    mkdirSync(dirname(OUTPUT_PATH), { recursive: true });
    generate(OUTPUT_PATH);
    console.log(`Generated ${OUTPUT_PATH} from ${SCHEMA_PATH}`);
    return;
  }

  const tempDir = mkdtempSync(join(tmpdir(), "ce-kit-generated-api-types-"));
  try {
    const tempOutput = join(tempDir, "platformApi.ts");
    generate(tempOutput);
    const candidate = readFileSync(tempOutput);
    const committed = existsSync(OUTPUT_PATH) ? readFileSync(OUTPUT_PATH) : null;
    if (committed === null || !committed.equals(candidate)) {
      console.error(
        `[APITYPES001] ${OUTPUT_PATH} is stale relative to ${SCHEMA_PATH}. ` +
          "Run: pnpm --filter @anytoolai/ce-kit generate-api-types",
      );
      process.exit(1);
    }
    console.log("Generated API types are current");
  } finally {
    rmSync(tempDir, { recursive: true, force: true });
  }
}

main();
