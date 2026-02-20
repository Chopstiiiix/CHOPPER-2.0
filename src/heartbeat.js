const fs = require('fs');
const path = require('path');
const os = require('os');

let timer = null;
let lastBeat = null;

function ts() {
  return new Date().toISOString();
}

function log(line) {
  try {
    fs.mkdirSync(path.resolve('logs'), { recursive: true });
    fs.appendFileSync(path.resolve('logs/heartbeat.log'), `${line}\n`, 'utf8');
  } catch (err) {
    console.warn(`[${ts()}] [HEARTBEAT] [WARN] ${err.message}`);
  }
}

async function maybePost(payload) {
  const url = process.env.HEARTBEAT_URL;
  if (!url) return;

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 5000);
  try {
    await fetch(url, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
  } catch (err) {
    log(`[${ts()}] [HEARTBEAT] [WARN] heartbeat POST failed: ${err.message}`);
  } finally {
    clearTimeout(timeout);
  }
}

async function pulse() {
  lastBeat = {
    timestamp: ts(),
    uptime: process.uptime(),
    rss: process.memoryUsage().rss,
    hostname: os.hostname(),
  };
  log(`[${lastBeat.timestamp}] [HEARTBEAT] beat uptime=${lastBeat.uptime.toFixed(1)} rss=${lastBeat.rss}`);
  await maybePost(lastBeat);
  return lastBeat;
}

function start() {
  const everyMs = parseInt(process.env.HEARTBEAT_INTERVAL_MS || '30000', 10);
  if (timer) return;
  pulse();
  timer = setInterval(() => {
    pulse().catch((err) => {
      log(`[${ts()}] [HEARTBEAT] [WARN] pulse failed: ${err.message}`);
    });
  }, everyMs);
}

function stop() {
  if (timer) {
    clearInterval(timer);
    timer = null;
  }
}

function getLastBeat() {
  return lastBeat;
}

if (process.argv.includes('--once')) {
  pulse().finally(() => process.exit(0));
}

module.exports = { start, stop, getLastBeat, pulse };
