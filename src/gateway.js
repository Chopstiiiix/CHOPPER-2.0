require('dotenv').config();

const express = require('express');
const fs = require('fs');
const path = require('path');
const scheduler = require('./scheduler');
const heartbeat = require('./heartbeat');
const watchdog = require('./connectivity-watchdog');
const inbox = require('./inbox');
const ralph = require('./ralph');
const memory = require('./memory');

const ENABLED = process.env.AUTONOMY_ENABLED === 'true';
const PORT = parseInt(process.env.GATEWAY_PORT || '3100', 10);

function ts() {
  return new Date().toISOString();
}

function log(message, level = 'INFO') {
  const line = `[${ts()}] [GATEWAY] [${level}] ${message}`;
  console.log(line);
  try {
    fs.mkdirSync(path.resolve('logs'), { recursive: true });
    fs.appendFileSync(path.resolve('logs/gateway.log'), `${line}\n`, 'utf8');
  } catch (err) {
    console.error(`[${ts()}] [GATEWAY] [WARN] Failed to write gateway log: ${err.message}`);
  }
}

function gracefulShutdown(server) {
  return () => {
    log('Shutdown signal received. Stopping subsystems...');
    try { scheduler.stop(); } catch (err) { log(`scheduler.stop failed: ${err.message}`, 'WARN'); }
    try { heartbeat.stop(); } catch (err) { log(`heartbeat.stop failed: ${err.message}`, 'WARN'); }
    try { watchdog.stop(); } catch (err) { log(`watchdog.stop failed: ${err.message}`, 'WARN'); }
    try { memory.save(); } catch (err) { log(`memory.save failed: ${err.message}`, 'WARN'); }

    if (server) {
      server.close(() => {
        log('Gateway shutdown complete.');
        process.exit(0);
      });
      setTimeout(() => process.exit(1), 5000);
    } else {
      process.exit(0);
    }
  };
}

async function boot() {
  try {
    if (!ENABLED) {
      log('Autonomy disabled (AUTONOMY_ENABLED != true). Exiting cleanly.');
      process.exit(0);
    }

    log('Booting autonomy subsystems...');

    watchdog.on('connectivity:lost', (payload) => {
      log(`Connectivity lost after ${payload.failures} failures`, 'WARN');
    });
    watchdog.on('connectivity:restored', () => {
      log('Connectivity restored');
    });

    watchdog.start();
    heartbeat.start();
    scheduler.start({ inbox, ralph, heartbeat, memory });

    const app = express();
    app.use(express.json({ limit: '1mb' }));

    app.get('/health', (_req, res) => {
      res.json({
        status: 'ok',
        uptime: process.uptime(),
        subsystems: {
          scheduler: scheduler.getStatus(),
          heartbeat: heartbeat.getLastBeat(),
          watchdog: watchdog.getStatus(),
          inbox: { size: inbox.size() },
        },
      });
    });

    app.post('/inbox', (req, res) => {
      try {
        const id = inbox.push(req.body || {});
        res.status(202).json({ accepted: true, id });
      } catch (err) {
        log(`Failed to enqueue inbound message: ${err.message}`, 'WARN');
        res.status(400).json({ error: err.message });
      }
    });

    const server = app.listen(PORT, () => {
      log(`Gateway listening on port ${PORT}`);
    });

    process.on('SIGTERM', gracefulShutdown(server));
    process.on('SIGINT', gracefulShutdown(server));
  } catch (err) {
    log(`Startup failure: ${err.stack || err.message}`, 'ERROR');
    process.exit(1);
  }
}

boot();
