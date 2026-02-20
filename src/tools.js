const fs = require('fs');
const path = require('path');
const os = require('os');

const registry = new Map();

function log(message, level = 'INFO') {
  const line = `[${new Date().toISOString()}] [TOOLS] [${level}] ${message}`;
  console.log(line);
  try {
    fs.mkdirSync(path.resolve('logs'), { recursive: true });
    fs.appendFileSync(path.resolve('logs/tools.log'), `${line}\n`, 'utf8');
  } catch (_) {}
}

function register(name, description, handler, isReadOnly = true) {
  registry.set(name, { name, description, isReadOnly, handler });
}

function list() {
  return Array.from(registry.values()).map((t) => ({
    name: t.name,
    description: t.description,
    isReadOnly: t.isReadOnly,
  }));
}

async function invoke(name, args = {}) {
  const tool = registry.get(name);
  if (!tool) throw new Error(`Unknown tool: ${name}`);
  if (!tool.isReadOnly && process.env.TOOLS_WRITE_ENABLED !== 'true') {
    throw new Error(`Tool '${name}' requires TOOLS_WRITE_ENABLED=true`);
  }

  log(`Invoking tool '${name}'`);
  const result = await Promise.resolve(tool.handler(args));
  return result;
}

register(
  'system-status',
  'Return CPU, memory, load average and uptime',
  () => ({
    hostname: os.hostname(),
    platform: process.platform,
    uptime: os.uptime(),
    totalMem: os.totalmem(),
    freeMem: os.freemem(),
    loadavg: os.loadavg(),
  }),
  true
);

register(
  'search-logs',
  'Search a log file under logs/ for a text pattern',
  ({ file = 'gateway.log', pattern = 'ERROR', maxLines = 50 }) => {
    const safeFile = path.basename(file);
    const logPath = path.resolve('logs', safeFile);
    if (!logPath.startsWith(path.resolve('logs'))) {
      throw new Error('Only logs/ directory is allowed');
    }
    if (!fs.existsSync(logPath)) {
      return [];
    }
    const content = fs.readFileSync(logPath, 'utf8').split('\n');
    return content.filter((line) => line.includes(pattern)).slice(-Math.max(1, Math.min(500, maxLines)));
  },
  true
);

register(
  'check-services',
  'Check Flask and gateway health endpoints',
  async () => {
    const urls = [
      process.env.FLASK_HEALTH_URL || 'http://127.0.0.1:8000/',
      `http://127.0.0.1:${process.env.GATEWAY_PORT || 3100}/health`,
    ];

    const results = {};
    for (const url of urls) {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 5000);
      try {
        const res = await fetch(url, { signal: controller.signal });
        results[url] = { ok: res.ok, status: res.status };
      } catch (err) {
        results[url] = { ok: false, error: err.message };
      } finally {
        clearTimeout(timeout);
      }
    }
    return results;
  },
  true
);

register(
  'read-memory',
  'Read agent memory file contents',
  () => {
    const p = path.resolve('instance/agent-memory.json');
    if (!fs.existsSync(p)) return {};
    return JSON.parse(fs.readFileSync(p, 'utf8'));
  },
  true
);

module.exports = { register, list, invoke };
