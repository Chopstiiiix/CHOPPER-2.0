const fs = require('fs');
const path = require('path');
const memory = require('./memory');
const tools = require('./tools');
const skills = require('./skills');

function log(message, level = 'INFO') {
  const line = `[${new Date().toISOString()}] [RALPH] [${level}] ${message}`;
  console.log(line);
  try {
    fs.mkdirSync(path.resolve('logs'), { recursive: true });
    fs.appendFileSync(path.resolve('logs/ralph-decisions.log'), `${line}\n`, 'utf8');
  } catch (_) {}
}

function rememberDecision(entry) {
  const history = memory.get('_taskHistory') || [];
  history.push(entry);
  memory.set('_taskHistory', history.slice(-500));
  memory.save();
}

function queueForReview(message, reason) {
  const review = memory.get('pending-review') || [];
  review.push({ message, reason, queuedAt: new Date().toISOString() });
  memory.set('pending-review', review.slice(-500));
  memory.save();
}

async function processMessage(message) {
  const body = String(message.body || '').trim();
  const decision = {
    id: message.id,
    source: message.source,
    action: 'pending-review',
    reason: 'No matching skill/tool command',
    timestamp: new Date().toISOString(),
  };

  try {
    if (body.startsWith('skill:')) {
      const name = body.replace('skill:', '').trim();
      const result = await skills.execute(name, { message });
      decision.action = 'skill';
      decision.reason = `Executed skill ${name}`;
      decision.result = result;
    } else if (body.startsWith('tool:')) {
      const name = body.replace('tool:', '').trim();
      const result = await tools.invoke(name, {});
      decision.action = 'tool';
      decision.reason = `Executed tool ${name}`;
      decision.result = result;
    } else {
      queueForReview(message, decision.reason);
    }

    if (process.env.RALPH_AUTOSEND !== 'true') {
      decision.autosend = false;
      decision.note = 'No outbound actions without RALPH_AUTOSEND=true';
    }

    rememberDecision(decision);
    log(`Decision for ${message.id}: ${decision.action} (${decision.reason})`);
    return decision;
  } catch (err) {
    const failed = {
      ...decision,
      action: 'failed',
      reason: err.message,
    };
    rememberDecision(failed);
    log(`Decision failed for ${message.id}: ${err.message}`, 'ERROR');
    throw err;
  }
}

async function processNext(inbox) {
  const msg = inbox.next();
  if (!msg) return null;

  try {
    const result = await processMessage(msg);
    msg.status = 'completed';
    return result;
  } catch (err) {
    msg.status = 'failed';
    return null;
  }
}

function getDecisionHistory(n = 20) {
  const history = memory.get('_taskHistory') || [];
  return history.slice(-Math.max(1, n));
}

module.exports = { processMessage, processNext, getDecisionHistory, tools, skills };
