// Use argument-based spawning rather than Pinokio 8.3.7's unquoted Windows
// venv activation commands, so a Pinokio home containing spaces also works.
const shell = (action, extra = {}) => ({
  method: "shell.run",
  params: {
    path: ".",
    env: { PYTHONNOUSERSITE: "1", PYTHONUTF8: "1", PYTHONUNBUFFERED: "1" },
    message: `node scripts/run.js ${action}`,
    on: [{ event: "/PIXLSTASH_ERROR|Traceback \\(most recent call last\\)/", break: true }],
    ...extra
  }
});
// 8.3.7's script.stop does not resolve relative URIs against the caller.
const stop = () => ({ method: "script.stop", params: { uri: require("path").join(__dirname, "start.js") } });
module.exports = { shell, stop };
