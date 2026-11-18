const { shell } = require("./launcher");
const path = require("node:path");
const { setTimeout: delay } = require("node:timers/promises");

const appFolder = path.basename(__dirname);
const stopShellId = `pixlstash-stop-${appFolder}`;

module.exports = {
  daemon: true,
  // A direct kernel request resolves its path from PINOKIO_HOME/api.
  on: { stop: shell("stop-server", { path: appFolder, id: stopShellId }) },
  run: [
    shell("serve", {
      on: [
        { event: "/PIXLSTASH_FATAL:/", done: true },
        // 8.3.7 scans the transcript for these substrings, including in
        // INFO logger names and recoverable warnings. The launcher reports
        // fatal startup and readiness failures explicitly.
        { event: "/error:|errno /i", break: false },
        { event: "/PIXLSTASH_READY=(http:\\/\\/[0-9.:]+)\\r?\\n/", done: true }
      ]
    }),
    {
      when: "{{input.event && input.event[1]}}",
      method: "local.set",
      params: { url: "{{input.event[1]}}", shellId: "{{input.id}}" }
    },
    {
      method: async (request, _ondata, kernel) => {
        // 8.3.7 leaves daemon state in memory when a detached PTY exits.
        // Wait on the original Pinokio shell and finish the script on exit.
        const id = request.parent.id || request.parent.path;
        const local = kernel.memory.local[id];
        let stopping = false;
        while (request.params.shellId && kernel.shell.get(request.params.shellId)) {
          stopping ||= Boolean(kernel.shell.get(stopShellId));
          await delay(500);
        }
        // Pinokio's Stop can already be waiting for the foreground process.
        // Let it finish clearing this run before another Start can go ahead.
        if (!stopping && !kernel.shell.get(stopShellId) && kernel.memory.local[id] === local) {
          delete local?.url;
          await kernel.api.stop({ params: { id } });
        }
      },
      params: { shellId: "{{local.shellId || ''}}" }
    }
  ]
};
