const { shell } = require("./launcher");
const path = require("node:path");

module.exports = {
  daemon: true,
  // Pinokio runs this hook before killing the shell tree. Its path is
  // resolved from PINOKIO_HOME/api because the hook is a direct kernel request.
  on: { stop: shell("stop-server", { path: path.basename(__dirname) }) },
  run: [
    shell("serve", {
      on: [
        { event: "/PIXLSTASH_FATAL:/", break: true },
        // 8.3.7 scans the transcript for these substrings, including in
        // INFO logger names and recoverable warnings. Use the launcher exit
        // and readiness diagnostics above to decide when serving has failed.
        { event: "/error:|errno /i", break: false },
        { event: "/PIXLSTASH_READY=(http:\\/\\/[0-9.:]+)\\r?\\n/", done: true }
      ]
    }),
    { when: "{{input.event && input.event[1]}}", method: "local.set", params: { url: "{{input.event[1]}}" } }
  ]
};
