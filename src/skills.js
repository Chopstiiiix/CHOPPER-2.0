const fs = require('fs');
const path = require('path');
const tools = require('./tools');
const memory = require('./memory');

const skills = new Map();

function log(message, level = 'INFO') {
  const line = `[${new Date().toISOString()}] [SKILLS] [${level}] ${message}`;
  console.log(line);
  try {
    fs.mkdirSync(path.resolve('logs'), { recursive: true });
    fs.appendFileSync(path.resolve('logs/skills.log'), `${line}\n`, 'utf8');
  } catch (_) {}
}

function register(name, description, steps) {
  skills.set(name, { name, description, steps });
}

function list() {
  return Array.from(skills.values()).map((s) => ({ name: s.name, description: s.description }));
}

async function execute(name, context = {}) {
  const skill = skills.get(name);
  if (!skill) throw new Error(`Unknown skill: ${name}`);

  log(`Executing skill '${name}'`);
  const results = [];
  for (const step of skill.steps) {
    if (step.type !== 'tool') continue;
    const output = await tools.invoke(step.name, step.args || context);
    results.push({ step: step.name, output });
  }

  return { name, results, ranAt: new Date().toISOString() };
}

register('daily-summary', 'Run system scan and save summary to memory', [
  { type: 'tool', name: 'system-status' },
  { type: 'tool', name: 'check-services' },
]);

register('health-check', 'Check health and connectivity', [
  { type: 'tool', name: 'check-services' },
  { type: 'tool', name: 'system-status' },
]);

register('log-review', 'Review errors and warnings from logs', [
  { type: 'tool', name: 'search-logs', args: { file: 'gateway.log', pattern: 'ERROR', maxLines: 100 } },
  { type: 'tool', name: 'search-logs', args: { file: 'scheduler.log', pattern: 'WARN', maxLines: 100 } },
]);

module.exports = { register, list, execute, tools, memory };
