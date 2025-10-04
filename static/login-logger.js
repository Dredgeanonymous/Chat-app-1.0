// login-logger.js
const Database = require('better-sqlite3');
const db = new Database('login_logs.db');
const bcrypt = require('bcryptjs');

db.exec(`
CREATE TABLE IF NOT EXISTS login_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT,
  username TEXT,
  ip TEXT,
  user_agent TEXT,
  session_id TEXT,
  outcome TEXT,
  mod_code_hash TEXT
);
`);

function getIp(req){
  // trust proxy only if you configured it
  return (req.headers['x-forwarded-for'] || req.socket.remoteAddress || '').split(',')[0].trim();
}

function logLogin({username, ip, user_agent, session_id, outcome, mod_code}) {
  const ts = new Date().toISOString();
  let mod_code_hash = null;
  if (mod_code) {
    // hash mod_code before saving (never store raw sensitive codes)
    const salt = bcrypt.genSaltSync(10);
    mod_code_hash = bcrypt.hashSync(mod_code, salt);
  }
  const stmt = db.prepare(`INSERT INTO login_logs
    (ts, username, ip, user_agent, session_id, outcome, mod_code_hash)
    VALUES(?,?,?,?,?,?,?)`);
  stmt.run(ts, username, ip, user_agent, session_id, outcome, mod_code_hash);
}

module.exports = { logLogin, getIp };
