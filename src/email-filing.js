const fs = require('fs');
const path = require('path');

let running = false;
let timer = null;
const stats = { scanned: 0, classified: 0, failed: 0 };

function log(message, level = 'INFO') {
  const line = `[${new Date().toISOString()}] [EMAIL] [${level}] ${message}`;
  console.log(line);
  try {
    fs.mkdirSync(path.resolve('logs'), { recursive: true });
    fs.appendFileSync(path.resolve('logs/email-filing.log'), `${line}\n`, 'utf8');
  } catch (_) {}
}

function classify(subject = '', body = '') {
  const text = `${subject} ${body}`.toLowerCase();
  if (/urgent|asap|immediately|critical/.test(text)) return 'urgent';
  if (/action|required|todo|approve|review/.test(text)) return 'action-required';
  if (/unsubscribe|winner|lottery|crypto giveaway/.test(text)) return 'spam';
  return 'informational';
}

async function runPollCycle(inbox) {
  stats.scanned += 1;

  if (!process.env.IMAP_HOST || !process.env.IMAP_USER || !process.env.IMAP_PASS) {
    log('IMAP credentials missing; skipping poll cycle', 'WARN');
    return;
  }

  const category = classify('health check', 'autonomy poll cycle placeholder');
  inbox.push({
    source: 'email',
    from: process.env.IMAP_USER,
    subject: 'Email poll heartbeat',
    body: `Email subsystem active. category=${category}`,
    priority: category === 'urgent' ? 1 : 5,
    status: 'pending',
  });
  stats.classified += 1;
}

function start(inbox) {
  if (process.env.EMAIL_ENABLED !== 'true') {
    log('Email filing disabled by configuration.');
    return;
  }
  if (running) return;
  running = true;
  log('Email filing started');
  timer = setInterval(() => {
    runPollCycle(inbox).catch((err) => {
      stats.failed += 1;
      log(`Email filing cycle failed: ${err.message}`, 'WARN');
    });
  }, 60_000);
}

function stop() {
  running = false;
  if (timer) {
    clearInterval(timer);
    timer = null;
  }
  log('Email filing stopped');
}

function getStats() {
  return { ...stats, running };
}

module.exports = { start, stop, getStats, classify };
