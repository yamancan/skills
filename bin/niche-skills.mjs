#!/usr/bin/env node
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { createInterface } from 'node:readline/promises';

const catalog = ['let-chinese', 'let-chinese-somehow', 'duo', 'orkestra', 'project-context'];
const args = process.argv.slice(2);
const selected = [];
const forwarded = [];
const flags = new Set(['-g', '--global', '-y', '--yes', '--copy', '-l', '--list']);
function fail(message) {
  console.error(`${message}\nThis shortcut installs skills. Update with: npx skills@latest update`);
  process.exit(2);
}
if (args.includes('--help') || args.includes('-h')) {
  console.log(`Niche Skills — by Yaman Can\nUsage: npx yamancan/skills [options]\n\n--skill, -s NAME...  Select skills (* selects all); Orkestra includes Duo\n--agent, -a NAME...  Choose agents, e.g. claude-code codex\n--global, -g        Install globally (default: current project)\n--copy              Copy instead of shared symlinks\n--yes, -y           Skip confirmation; requires explicit skills and agents\n--list, -l          List the collection without installing\n\nAvailable: ${catalog.join(', ')}\nUpdate: npx skills@latest update`);
  process.exit(0);
}
for (let i = 0; i < args.length; i++) {
  const arg = args[i];
  if (['--skill', '-s', '--agent', '-a'].includes(arg)) {
    const values = [];
    while (i + 1 < args.length && !args[i + 1].startsWith('-')) values.push(args[++i]);
    if (!values.length) fail(`${arg} needs a value.`);
    if (arg === '--skill' || arg === '-s') selected.push(...values);
    else forwarded.push(arg, ...values);
  } else if (flags.has(arg)) forwarded.push(arg);
  else fail(`Unsupported argument: ${arg}`);
}
const listing = forwarded.includes('--list') || forwarded.includes('-l');
const unattended = !process.stdin.isTTY || !process.stdout.isTTY || forwarded.includes('-y') || forwarded.includes('--yes');
if (!selected.length && !listing) {
  if (unattended) {
    fail('Choose skills explicitly, e.g. --skill duo or --skill orkestra.');
  }
  const terminal = createInterface({ input: process.stdin, output: process.stdout });
  let answered = false;
  terminal.on('SIGINT', () => fail('Selection cancelled.'));
  terminal.on('close', () => { if (!answered) fail('Selection cancelled.'); });
  try {
    const answer = await terminal.question(`${catalog.map((name, i) => `${i + 1}. ${name}`).join('\n')}\nChoose names or numbers (comma-separated; * for all): `);
    answered = true;
    selected.push(...answer.trim().split(/[,\s]+/).filter(Boolean).map(value => catalog[Number(value) - 1] ?? value));
  } finally {
    terminal.close();
  }
  if (!selected.length) fail('No skills selected.');
}
for (const name of selected) if (name !== '*' && !catalog.includes(name)) fail(`Unknown skill: ${name}`);
if (!listing && unattended && !forwarded.includes('--agent') && !forwarded.includes('-a')) {
  fail('Choose target agents explicitly, e.g. --agent claude-code codex.');
}
const skills = new Set(selected.includes('*') ? catalog : selected);
if (skills.has('orkestra')) skills.add('duo');
if (skills.size) forwarded.push('--skill', ...skills);

const installer = createRequire(import.meta.url).resolve('skills/bin/cli.mjs');
const child = spawnSync(process.execPath, [installer, 'add', 'yamancan/skills', ...forwarded], {
  stdio: 'inherit',
  env: { ...process.env, DISABLE_TELEMETRY: '1' },
});
if (child.error) console.error(`Could not start Skills CLI: ${child.error.message}`);
process.exit(child.status ?? 1);
