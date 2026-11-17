// Pinokio supplies Node and uv. All downloads and Python packages belong to this app.
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const python = path.join(root, "env", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const args = process.argv.slice(2);
const env = {
  ...process.env,
  PYTHONNOUSERSITE: "1", PYTHONUTF8: "1", PYTHONUNBUFFERED: "1",
  PYTHONHOME: "", PYTHONPATH: "",
  UV_CACHE_DIR: path.join(root, "cache", "uv"),
  UV_PYTHON_INSTALL_DIR: path.join(root, "cache", "python")
};

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

(async () => {
  if (!fs.existsSync(python)) {
    if (args[0] !== "install") throw new Error("Install PixlStash first.");
    // Request managed Python, rather than inheriting a user's Conda or system Python.
    await run("uv", ["venv", path.join(root, "env"), "--python", "3.12", "--managed-python"]);
  }
  await run(python, ["-s", "-u", path.join(root, "scripts", "manage.py"), ...args]);
})().catch(error => {
  console.error(`PIXLSTASH_ERROR: ${error.message}`);
  process.exitCode = 1;
});
