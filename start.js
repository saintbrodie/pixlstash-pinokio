const { shell } = require("./launcher");
module.exports = {
  daemon: true,
  run: [
    shell("serve", {
      on: [
        { event: "/PIXLSTASH_READY=(http:\\/\\/127\\.0\\.0\\.1:[0-9]+)/", done: true },
        { event: "/PIXLSTASH_ERROR|Traceback \\(most recent call last\\)/", break: true }
      ]
    }),
    { method: "local.set", params: { url: "{{input.event[1]}}" } }
  ]
};
