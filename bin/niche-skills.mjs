#!/usr/bin/env node
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';

const installer = createRequire(import.meta.url).resolve('skills/bin/cli.mjs');
const child = spawnSync(process.execPath, [installer, 'add', 'yamancan/skills', ...process.argv.slice(2)], {
  stdio: 'inherit',
});
if (child.error) console.error(`Could not start Skills CLI: ${child.error.message}`);
process.exit(child.status ?? 1);
