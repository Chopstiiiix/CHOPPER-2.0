const fs = require('fs');
const path = require('path');

const memoryPath = path.resolve('instance/agent-memory.json');
const maxBytes = 5 * 1024 * 1024;
const state = {
  _version: '1.0.0',
  _lastBoot: new Date().toISOString(),
  _taskHistory: [],
};

let autosaveTimer = null;
let writeInProgress = false;

function log(message, level = 'INFO') {
  const line = `[${new Date().toISOString()}] [MEMORY] [${level}] ${message}`;
  console.log(line);
  try {
    fs.mkdirSync(path.resolve('logs'), { recursive: true });
    fs.appendFileSync(path.resolve('logs/memory.log'), `${line}\n`, 'utf8');
  } catch (_) {}
}

function load() {
  try {
    if (!fs.existsSync(memoryPath)) {
      fs.mkdirSync(path.dirname(memoryPath), { recursive: true });
      save();
      return state;
    }
    const raw = fs.readFileSync(memoryPath, 'utf8');
    const parsed = JSON.parse(raw);
    Object.assign(state, parsed, { _lastBoot: new Date().toISOString() });
    return state;
  } catch (err) {
    log(`Failed to load memory: ${err.message}`, 'WARN');
    return state;
  }
}

function save() {
  if (writeInProgress) return false;
  const serialized = JSON.stringify(state, null, 2);
  if (Buffer.byteLength(serialized, 'utf8') > maxBytes) {
    log('Memory file exceeds 5MB; refusing write', 'WARN');
    return false;
  }

  writeInProgress = true;
  try {
    fs.mkdirSync(path.dirname(memoryPath), { recursive: true });
    const tmp = `${memoryPath}.tmp`;
    fs.writeFileSync(tmp, serialized, 'utf8');
    fs.renameSync(tmp, memoryPath);
    return true;
  } catch (err) {
    log(`Failed to save memory: ${err.message}`, 'WARN');
    return false;
  } finally {
    writeInProgress = false;
  }
}

function get(key) {
  return state[key];
}

function set(key, value) {
  state[key] = value;
  return true;
}

function del(key) {
  delete state[key];
  return true;
}

function getAll() {
  return { ...state };
}

function startAutosave() {
  const intervalMs = parseInt(process.env.MEMORY_AUTOSAVE_MS || '60000', 10);
  if (autosaveTimer) return;
  autosaveTimer = setInterval(() => save(), intervalMs);
}

function stopAutosave() {
  if (autosaveTimer) {
    clearInterval(autosaveTimer);
    autosaveTimer = null;
  }
}

load();
startAutosave();

module.exports = {
  get,
  set,
  delete: del,
  getAll,
  save,
  load,
  stopAutosave,
};
