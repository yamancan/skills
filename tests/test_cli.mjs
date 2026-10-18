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
  const result = spawnSync(process.execPath, [f.launcher, '--skill', 'duo', '-a', literal, '-g'], {
    cwd: f.root, env: { ...process.env, ARGV_CAPTURE: f.capture }, encoding: 'utf8', timeout: 5000,
  });
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(JSON.parse(readFileSync(f.capture)), ['add', 'yamancan/skills', '-a', literal, '-g', '--skill', 'duo']);
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

test('selecting Orkestra includes its Duo companion once and preserves the chosen agents and scope', t => {
  const f = fixture(t);
  const result = spawnSync(process.execPath, [f.launcher, '--skill', 'orkestra', '-a', 'claude-code', 'codex', '-g', '-y'], {
    env: { ...process.env, ARGV_CAPTURE: f.capture }, encoding: 'utf8', timeout: 5000,
  });
  assert.equal(result.status, 0, result.stderr);
  const args = JSON.parse(readFileSync(f.capture));
  assert.ok(args.includes('duo'), 'Duo must accompany Orkestra');
  assert.equal(args.filter(arg => arg === 'duo').length, 1);
  assert.ok(args.includes('orkestra') && args.includes('claude-code') && args.includes('codex') && args.includes('-g'));
});

test('unsupported commands stop before the installer can write anything', t => {
  const f = fixture(t);
  const result = spawnSync(process.execPath, [f.launcher, 'update', '-a', 'codex', '-y'], {
    env: { ...process.env, ARGV_CAPTURE: f.capture }, encoding: 'utf8', timeout: 5000,
  });
  assert.equal(result.status, 2);
  assert.equal(existsSync(f.capture), false);
  assert.match(result.stderr, /skills@latest update/);
});

test('an unattended install requires explicit skill selection instead of installing the whole collection', t => {
  const f = fixture(t);
  const result = spawnSync(process.execPath, [f.launcher, '-y'], {
    env: { ...process.env, ARGV_CAPTURE: f.capture }, encoding: 'utf8', timeout: 5000,
  });
  assert.equal(result.status, 2);
  assert.equal(existsSync(f.capture), false);
});

test('malformed install requests fail before any installer side effects', t => {
  for (const args of [['--skill'], ['--agent'], ['--skill', 'unknown'], ['--unknown'], ['--skill=orkestra']]) {
    const f = fixture(t);
    const result = spawnSync(process.execPath, [f.launcher, ...args], {
      env: { ...process.env, ARGV_CAPTURE: f.capture }, encoding: 'utf8', timeout: 5000,
    });
    assert.equal(result.status, 2, String(args));
    assert.equal(existsSync(f.capture), false);
  }
});

test('unattended selection also requires an explicit target agent', t => {
  const f = fixture(t);
  const result = spawnSync(process.execPath, [f.launcher, '--skill', 'duo', '-y'], {
    env: { ...process.env, ARGV_CAPTURE: f.capture }, encoding: 'utf8', timeout: 5000,
  });
  assert.equal(result.status, 2);
  assert.equal(existsSync(f.capture), false);
});
