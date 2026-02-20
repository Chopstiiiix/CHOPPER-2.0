const fs = require('fs');
const path = require('path');
const EventEmitter = require('events');

class ConnectivityWatchdog extends EventEmitter {
  constructor() {
    super();
    this.interval = null;
    this.failures = 0;
    this.connected = true;
    this.lastCheckAt = null;
  }

  _log(message, level = 'INFO') {
    const line = `[${new Date().toISOString()}] [WATCHDOG] [${level}] ${message}`;
    console.log(line);
    try {
      fs.mkdirSync(path.resolve('logs'), { recursive: true });
      fs.appendFileSync(path.resolve('logs/watchdog.log'), `${line}\n`, 'utf8');
    } catch (_) {}
  }

  async _check() {
    const url = process.env.WATCHDOG_PING_URL || 'https://api.anthropic.com';
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);

    this.lastCheckAt = new Date().toISOString();
    try {
      const res = await fetch(url, { method: 'HEAD', signal: controller.signal });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const wasDisconnected = !this.connected;
      this.connected = true;
      this.failures = 0;
      if (wasDisconnected) {
        this.emit('connectivity:restored');
        this._log('Connectivity restored');
      }
    } catch (err) {
      this.failures += 1;
      this.connected = false;
      this._log(`Connectivity check failed (${this.failures}): ${err.message}`, 'WARN');
      if (this.failures === 3) {
        this.emit('connectivity:lost', { failures: this.failures });
        this._log('Connectivity lost threshold reached', 'ERROR');
      }
    } finally {
      clearTimeout(timeout);
    }
  }

  start() {
    const everyMs = parseInt(process.env.WATCHDOG_INTERVAL_MS || '60000', 10);
    if (this.interval) return;
    this._check();
    this.interval = setInterval(() => {
      this._check().catch((err) => this._log(`Unexpected watchdog error: ${err.message}`, 'WARN'));
    }, everyMs);
  }

  stop() {
    if (this.interval) {
      clearInterval(this.interval);
      this.interval = null;
    }
  }

  getStatus() {
    return {
      connected: this.connected,
      failures: this.failures,
      lastCheckAt: this.lastCheckAt,
    };
  }
}

module.exports = new ConnectivityWatchdog();
