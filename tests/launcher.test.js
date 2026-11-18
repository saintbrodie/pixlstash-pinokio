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

test("first run offers manual CPU and NVIDIA setup", async () => {
  const uninstalled = await launcher.menu({}, info());
  assert.deepEqual(uninstalled.map(item => item.href), ["install.js", "nvidia.js"]);
  assert.ok(uninstalled.every(item => !item.default));
  assert.equal(require("../nvidia").run[1].params.message, "node scripts/run.js install --backend nvidia");
});

test("completed installation offers manual Start and maintenance actions", async () => {
  const stopped = await launcher.menu({}, info({ installed: true, url: "http://127.0.0.1:9537" }));
  assert.deepEqual(stopped.map(item => item.href), ["start.js", "update.js", "nvidia.js", "cpu.js"]);
  assert.ok(stopped.every(item => !item.default));
});

test("readiness offers the captured URL in an external browser and keeps Stop available", async () => {
  const starting = await launcher.menu({}, info({ installed: true, running: ["start.js"] }));
  assert.deepEqual(starting.map(item => item.href), ["start.js", "stop.js"]);
  assert.ok(starting.every(item => !item.default));
  assert.match(starting[0].text, /Starting PixlStash/);
  const url = "http://127.0.0.1:49281";
  const online = await launcher.menu({}, info({ running: ["start.js"], url }));
  assert.deepEqual(online.map(item => item.href), [url, "start.js", "stop.js"]);
  assert.equal(online[0].popout, true);
  assert.ok(online.every(item => !item.default));
});

test("mutating actions hide competing actions while working", async () => {
  for (const script of ["install.js", "update.js", "nvidia.js", "cpu.js", "stop.js"]) {
    const menu = await launcher.menu({}, info({ installed: true, running: [script] }));
    assert.equal(menu.length, 1);
    assert.equal(menu[0].href, script);
    assert.ok(!menu[0].default);
  }
});

test("readiness only matches the verified loopback URL, not download URLs", () => {
  const { event } = start.run[0].params.on.find(handler => handler.event.includes("PIXLSTASH_READY"));
  const regex = new RegExp(event.slice(1, -1));
  assert.equal(regex.exec("Downloading https://huggingface.co/models"), null);
  assert.equal(regex.exec("uvicorn.error: Uvicorn running on http://127.0.0.1:9537\n"), null);
  assert.equal(regex.exec("PIXLSTASH_READY=http://127.0.0.1:1953"), null);
  assert.equal(regex.exec("PIXLSTASH_READY=http://127.0.0.1:19537\n")[1], "http://127.0.0.1:19537");
  assert.equal(start.run[1].params.url, "{{input.event[1]}}");
});

test("Pinokio ignores generic server logs and routes fatal signals to cleanup", () => {
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
    return /error:|errno /i.test(text) || handlers.some(handler => handler.done && pattern(handler).test(text));
  }
  assert.equal(fatal("INFO: uvicorn.error: Uvicorn running on http://127.0.0.1:9537"), false);
  assert.equal(fatal("WARNING: model download retry after OSError: [Errno 10060]"), false);
  assert.equal(fatal("Traceback (most recent call last):\nRuntimeError: bad config\nPIXLSTASH_FATAL: Initialization failed"), true);
  assert.equal(fatal("PIXLSTASH_FATAL: WebUI readiness timed out"), true);
});

test("daemon state is cleared when the Pinokio shell exits", async () => {
  const id = path.resolve(__dirname, "../start.js");
  const stopShellId = start.on.stop.params.id;
  let checks = 0;
  let stopping = false;
  const stopped = [];
  const kernel = {
    memory: { local: { [id]: { url: "http://127.0.0.1:9537" } } },
    shell: { get: shellId => {
      if (shellId === stopShellId) return stopping;
      assert.equal(shellId, "test-shell");
      return checks++ === 0;
    } },
    api: { stop: request => {
      assert.equal(kernel.memory.local[id].url, undefined);
      stopped.push(request.params.id);
    } }
  };
  const finish = start.run[2].method;
  await finish({ params: { shellId: "test-shell" }, parent: { id } }, null, kernel);
  assert.equal(checks, 2);
  await finish({ params: { shellId: "" }, parent: { path: id } }, null, kernel);
  assert.deepEqual(stopped, [id, id]);
  stopping = true;
  checks = 0;
  await finish({ params: { shellId: "test-shell" }, parent: { id } }, null, kernel);
  assert.deepEqual(stopped, [id, id]);
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
