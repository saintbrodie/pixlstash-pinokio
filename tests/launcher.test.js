const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const launcher = require("../pinokio");

function info({ installed = false, running = [], url } = {}) {
  return {
    exists: (...parts) => installed && parts.join("/") === "env/pixlstash-installed.json",
    running: script => running.includes(script),
    local: () => ({ url })
  };
}

test("first run offers installation, completed installation offers Start", async () => {
  assert.equal((await launcher.menu({}, info()))[0].href, "install.js");
  assert.equal((await launcher.menu({}, info({ installed: true })))[0].href, "start.js");
});

test("starting has no WebUI link; readiness supplies captured URL and Stop", async () => {
  const starting = await launcher.menu({}, info({ installed: true, running: ["start.js"] }));
  assert.deepEqual(starting.map(item => item.href), ["start.js", "stop.js"]);
  const url = "http://127.0.0.1:49281";
  const online = await launcher.menu({}, info({ running: ["start.js"], url }));
  assert.equal(online[0].href, url);
  assert.equal(online[0].default, true);
});

test("mutating actions hide competing actions while working", async () => {
  for (const script of ["install.js", "update.js", "nvidia.js", "cpu.js", "stop.js"]) {
    const menu = await launcher.menu({}, info({ installed: true, running: [script] }));
    assert.equal(menu.length, 1);
    assert.equal(menu[0].href, script);
  }
});

test("readiness only matches the verified loopback URL, not download URLs", () => {
  const event = require("../start").run[0].params.on[0].event;
  const regex = new RegExp(event.slice(1, -1));
  assert.equal(regex.exec("Downloading https://huggingface.co/models"), null);
  assert.equal(regex.exec("PIXLSTASH_READY=http://127.0.0.1:19537")[1], "http://127.0.0.1:19537");
});

test("stop targets this launcher's absolute path, including on Pinokio 8.3.7", async () => {
  const stop = require("../stop").run[0];
  assert.equal(stop.params.uri, path.resolve(__dirname, "../start.js"));
  // When available, invoke the actual installed script API extracted for local QA.
  const runtime = "../.runtime/node_modules/pinokiod/kernel/api/script";
  if (require("node:fs").existsSync(path.resolve(__dirname, runtime + "/index.js"))) {
    const Script = require(runtime);
    let stopped;
    await new Script().stop({ params: stop.params }, () => {}, {
      api: { stop: request => { stopped = request.params.uri; } }
    });
    assert.equal(stopped, stop.params.uri);
  }
});
