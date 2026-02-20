const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const queue = [];
let processedThisWindow = 0;
let windowStarted = Date.now();

const persistPath = path.resolve('logs/inbox-queue.json');
const maxSize = parseInt(process.env.INBOX_MAX_SIZE || '100', 10);
const ratePerMinute = parseInt(process.env.INBOX_RATE_LIMIT || '10', 10);

function log(message, level = 'INFO') {
  const line = `[${new Date().toISOString()}] [INBOX] [${level}] ${message}`;
  console.log(line);
  try {
    fs.mkdirSync(path.resolve('logs'), { recursive: true });
    fs.appendFileSync(path.resolve('logs/inbox.log'), `${line}\n`, 'utf8');
  } catch (_) {}
}

function persist() {
  try {
    fs.mkdirSync(path.resolve('logs'), { recursive: true });
    fs.writeFileSync(persistPath, JSON.stringify(queue, null, 2), 'utf8');
  } catch (err) {
    log(`Failed to persist inbox queue: ${err.message}`, 'WARN');
  }
}

function normalize(input) {
  const now = new Date().toISOString();
  return {
    id: input.id || crypto.randomUUID(),
    source: input.source || 'internal',
    from: input.from || 'unknown',
    subject: input.subject || '',
    body: input.body || '',
    timestamp: input.timestamp || now,
    priority: Number.isFinite(input.priority) ? input.priority : 5,
    status: input.status || 'pending',
  };
}

function push(message) {
  const item = normalize(message || {});
  if (!item.body && !item.subject) {
    throw new Error('Message must include subject or body');
  }

  queue.push(item);
  queue.sort((a, b) => a.priority - b.priority);
  if (queue.length > maxSize) {
    const dropped = queue.shift();
    log(`Queue overflow. Dropped oldest message ${dropped.id}`, 'WARN');
  }
  persist();
  return item.id;
}

function _rateAllowed() {
  const now = Date.now();
  if (now - windowStarted >= 60_000) {
    processedThisWindow = 0;
    windowStarted = now;
  }
  if (processedThisWindow >= ratePerMinute) {
    return false;
  }
  processedThisWindow += 1;
  return true;
}

function next() {
  if (!_rateAllowed()) {
    log('Rate limit reached; delaying message processing', 'WARN');
    return null;
  }
  const item = queue.find((q) => q.status === 'pending');
  if (!item) return null;
  item.status = 'processing';
  persist();
  return item;
}

function peek() {
  return queue.find((q) => q.status === 'pending') || null;
}

function size() {
  return queue.length;
}

function drain() {
  const remaining = [...queue];
  queue.length = 0;
  persist();
  return remaining;
}

module.exports = { push, next, peek, size, drain };
