import assert from 'node:assert/strict';
import { test } from 'node:test';
import { mkdtempSync, mkdirSync, copyFileSync, writeFileSync, readFileSync, existsSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

// Only the external installer is replaced; the published launcher runs as a real process.
function fixture(t, exitCode = 0) {
  const root = mkdtempSync(join(tmpdir(), "niche cli ' "));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  const bin = join(root, 'bin');
  const dependency = join(root, 'node_modules/skills/bin');
  mkdirSync(bin);
  mkdirSync(dependency, { recursive: true });
  const launcher = fileURLToPath(new URL('../bin/niche-skills.mjs', import.meta.url));
  assert.ok(existsSync(launcher), 'The install shortcut must exist');
  copyFileSync(launcher, join(bin, 'niche-skills.mjs'));
  writeFileSync(join(dependency, 'cli.mjs'), `
    import { writeFileSync } from 'node:fs';
    writeFileSync(process.env.ARGV_CAPTURE, JSON.stringify(process.argv.slice(2)));
    console.error('installer status');
    process.exit(${exitCode});
  `);
  return { root, launcher: join(bin, 'niche-skills.mjs'), capture: join(root, 'args.json') };
}

test('installs the canonical collection and preserves literal selection arguments without shell execution', t => {
  const f = fixture(t);
  const marker = join(f.root, 'unexpected');
  const literal = `$(touch '${marker}')`;
  const result = spawnSync(process.execPath, [f.launcher, '--skill', literal, '-a', 'claude-code', '-a', 'codex', '-g'], {
    cwd: f.root, env: { ...process.env, ARGV_CAPTURE: f.capture }, encoding: 'utf8', timeout: 5000,
  });
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(JSON.parse(readFileSync(f.capture)), ['add', 'yamancan/skills', '--skill', literal, '-a', 'claude-code', '-a', 'codex', '-g']);
  assert.equal(existsSync(marker), false);
});

test('reports installer failure instead of claiming installation succeeded', t => {
  const f = fixture(t, 23);
  const result = spawnSync(process.execPath, [f.launcher, '--list'], {
    env: { ...process.env, ARGV_CAPTURE: f.capture }, encoding: 'utf8', timeout: 5000,
  });
  assert.equal(result.status, 23);
  assert.match(result.stderr, /installer status/);
});
