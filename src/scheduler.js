const fs = require('fs');
const path = require('path');
const cron = require('node-cron');

const jobs = new Map();
let started = false;

function ts() {
  return new Date().toISOString();
}

function log(message, level = 'INFO') {
  const line = `[${ts()}] [SCHEDULER] [${level}] ${message}`;
  console.log(line);
  try {
    fs.mkdirSync(path.resolve('logs'), { recursive: true });
    fs.appendFileSync(path.resolve('logs/scheduler.log'), `${line}\n`, 'utf8');
  } catch (_) {}
}

function enabled() {
  if (process.env.SCHEDULER_ENABLED) {
    return process.env.SCHEDULER_ENABLED === 'true';
  }
  return process.env.AUTONOMY_ENABLED === 'true';
}

function loadTaskDefinitions() {
  const taskFile = path.resolve('cron/alex-tasks');
  try {
    const raw = fs.readFileSync(taskFile, 'utf8');
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed.tasks) ? parsed.tasks : [];
  } catch (err) {
    log(`Failed to load task definitions: ${err.message}`, 'WARN');
    return [];
  }
}

function resolveHandler(handlerKey, modules) {
  if (!handlerKey || typeof handlerKey !== 'string') {
    return null;
  }

  if (handlerKey === 'heartbeat.pulse') {
    return async () => modules.heartbeat.pulse();
  }
  if (handlerKey === 'memory.save') {
    return async () => modules.memory.save();
  }
  if (handlerKey === 'ralph.processNext') {
    return async () => modules.ralph.processNext(modules.inbox);
  }
  if (handlerKey.startsWith('tools.invoke:')) {
    const toolName = handlerKey.split(':')[1];
    return async () => modules.ralph.tools.invoke(toolName, {});
  }
  if (handlerKey.startsWith('skills.execute:')) {
    const skillName = handlerKey.split(':')[1];
    return async () => modules.ralph.skills.execute(skillName, {});
  }
  return null;
}

function register(name, cronExpr, handler) {
  if (!cron.validate(cronExpr)) {
    throw new Error(`Invalid cron expression for ${name}: ${cronExpr}`);
  }

  if (jobs.has(name)) {
    jobs.get(name).stop();
    jobs.delete(name);
  }

  const job = cron.schedule(cronExpr, async () => {
    const start = Date.now();
    log(`Task '${name}' started`);
    try {
      await Promise.resolve(handler());
      const duration = Date.now() - start;
      log(`Task '${name}' succeeded (${duration}ms)`);
    } catch (err) {
      const duration = Date.now() - start;
      log(`Task '${name}' failed (${duration}ms): ${err.message}`, 'ERROR');
    }
  });

  jobs.set(name, job);
  return true;
}

function start(modules = {}) {
  if (started) return;
  if (!enabled()) {
    log('Scheduler disabled by configuration.');
    return;
  }

  const defs = loadTaskDefinitions();
  defs.filter((t) => t.enabled).forEach((task) => {
    const fn = resolveHandler(task.handler, modules);
    if (!fn) {
      log(`Unknown handler for task '${task.name}': ${task.handler}`, 'WARN');
      return;
    }
    try {
      register(task.name, task.cron, fn);
    } catch (err) {
      log(`Failed to register task '${task.name}': ${err.message}`, 'WARN');
    }
  });

  started = true;
  log(`Scheduler started with ${jobs.size} tasks.`);
}

function stop() {
  jobs.forEach((job) => job.stop());
  jobs.clear();
  started = false;
  log('Scheduler stopped.');
}

function listTasks() {
  return Array.from(jobs.keys());
}

function getStatus() {
  return {
    enabled: enabled(),
    started,
    tasks: listTasks(),
  };
}

module.exports = { start, stop, register, listTasks, getStatus };
