/** Experimental supporting collector; not an independent ANY-624 acceptance decision.
 * Scope and limitations: docs/exec-plans/active/any-624-update-model-comparison.md.
 */
import { chromium } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { collectLive } from './collect-live-run.mjs';

const spec = JSON.parse(readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify(await collectLive(spec, { chromium })));
