const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const launcher = require("../pinokio");
const start = require("../start");

function info({ installed = false, running = [], url } = {}) {
  return {
    exists: file => installed && file === "env/pixlstash-installed.json",
    running: script => running.includes(script),
    local: () => ({ url })
  };
}

test("first run offers installation, completed installation offers all actions", async () => {
  assert.equal((await launcher.menu({}, info()))[0].href, "install.js");
  const stopped = await launcher.menu({}, info({ installed: true, url: "http://127.0.0.1:9537" }));
  assert.deepEqual(stopped.map(item => item.href), ["start.js", "update.js", "nvidia.js", "cpu.js"]);
});

test("starting has no WebUI link; readiness supplies captured URL and Stop", async () => {
  const starting = await launcher.menu({}, info({ installed: true, running: ["start.js"] }));
  assert.deepEqual(starting.map(item => item.href), ["start.js", "stop.js"]);
  assert.equal(starting[0].default, true);
  assert.match(starting[0].text, /Starting PixlStash/);
  const url = "http://127.0.0.1:49281";
  const online = await launcher.menu({}, info({ running: ["start.js"], url }));
  assert.deepEqual(online.map(item => item.href), [url, "start.js", "stop.js"]);
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
  const { event } = start.run[0].params.on.find(handler => handler.done);
  const regex = new RegExp(event.slice(1, -1));
  assert.equal(regex.exec("Downloading https://huggingface.co/models"), null);
  assert.equal(regex.exec("uvicorn.error: Uvicorn running on http://127.0.0.1:9537\n"), null);
  assert.equal(regex.exec("PIXLSTASH_READY=http://127.0.0.1:1953"), null);
  assert.equal(regex.exec("PIXLSTASH_READY=http://127.0.0.1:19537\n")[1], "http://127.0.0.1:19537");
  assert.equal(start.run[1].params.url, "{{input.event[1]}}");
});

test("Pinokio ignores generic server logs but stops for the launcher's fatal signal", () => {
  const handlers = start.run[0].params.on;
  const pattern = ({ event }) => {
    const end = event.lastIndexOf("/");
    return new RegExp(event.slice(1, end), event.slice(end + 1) + "g");
  };
  // Pinokio 8.3.7 strips the break:false matches before scanning either
  // the live terminal buffer or the full response for break:true matches.
  function fatal(text) {
    for (const handler of handlers.filter(handler => handler.break === false)) {
      text = text.replace(pattern(handler), "");
    }
    return /error:|errno /i.test(text) || handlers.some(handler => handler.break && pattern(handler).test(text));
  }
  assert.equal(fatal("INFO: uvicorn.error: Uvicorn running on http://127.0.0.1:9537"), false);
  assert.equal(fatal("WARNING: model download retry after OSError: [Errno 10060]"), false);
  assert.equal(fatal("Traceback (most recent call last):\nRuntimeError: bad config\nPIXLSTASH_FATAL: Initialization failed"), true);
  assert.equal(fatal("PIXLSTASH_FATAL: WebUI readiness timed out"), true);
});

test("stop targets this launcher's absolute path, including on Pinokio 8.3.7", async () => {
  const stop = require("../stop").run[0];
  assert.equal(stop.params.uri, path.resolve(__dirname, "../start.js"));
  assert.equal(start.on.stop.params.path, path.basename(path.resolve(__dirname, "..")));
  assert.equal(start.on.stop.params.message, "node scripts/run.js stop-server");
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
