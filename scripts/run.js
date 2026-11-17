// Pinokio supplies Node and uv. All downloads and Python packages belong to this app.
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const python = path.join(root, "env", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const args = process.argv.slice(2);

function isolatedEnvironment(parent = process.env) {
  const env = {
    ...parent,
    PYTHONNOUSERSITE: "1", PYTHONUTF8: "1", PYTHONUNBUFFERED: "1",
    PYTHONHOME: "", PYTHONPATH: "",
    UV_CACHE_DIR: path.join(root, "cache", "uv"),
    UV_PYTHON_INSTALL_DIR: path.join(root, "cache", "python"),
    // Pinokio may set UV_PYTHON_PREFERENCE. Use a single, explicit preference
    // instead of combining it with uv's conflicting --managed-python switch.
    UV_PYTHON_PREFERENCE: "only-managed"
  };
  // These boolean uv switches conflict with UV_PYTHON_PREFERENCE if inherited.
  delete env.UV_MANAGED_PYTHON;
  delete env.UV_NO_MANAGED_PYTHON;
  return env;
}

function venvArgs() {
  return ["venv", path.join(root, "env"), "--python", "3.12"];
}

const env = isolatedEnvironment();

function run(command, argv) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, argv, { cwd: root, env, stdio: "inherit", windowsHide: true });
    child.once("error", reject);
    child.once("exit", (code, signal) => {
      if (code === 0) resolve();
      else reject(new Error(`${path.basename(command)} exited with ${signal || code}`));
    });
  });
}

async function main() {
  if (!fs.existsSync(python)) {
    if (args[0] !== "install") throw new Error("Install PixlStash first.");
    // A private uv-managed Python 3.12, never Pinokio's Conda/system interpreter.
    await run("uv", venvArgs());
  }
  await run(python, ["-s", "-u", path.join(root, "scripts", "manage.py"), ...args]);
}

if (require.main === module) {
  main().catch(error => {
    console.error(`PIXLSTASH_ERROR: ${error.message}`);
    process.exitCode = 1;
  });
}

module.exports = { isolatedEnvironment, venvArgs };
