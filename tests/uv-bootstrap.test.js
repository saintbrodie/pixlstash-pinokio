const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const { isolatedEnvironment, venvArgs } = require("../scripts/run");

test("uv bootstrap ignores conflicting Python preferences inherited from Pinokio", () => {
  const env = isolatedEnvironment({
    PATH: "C:\\Pinokio\\bin",
    UV_PYTHON_PREFERENCE: "only-system",
    UV_MANAGED_PYTHON: "1",
    UV_NO_MANAGED_PYTHON: "1",
    UV_CACHE_DIR: "C:\\other-app\\cache",
    UV_PYTHON_INSTALL_DIR: "C:\\other-app\\python"
  });
  assert.equal(env.PATH, "C:\\Pinokio\\bin");
  assert.equal(env.UV_PYTHON_PREFERENCE, "only-managed");
  assert.equal(Object.hasOwn(env, "UV_MANAGED_PYTHON"), false);
  assert.equal(Object.hasOwn(env, "UV_NO_MANAGED_PYTHON"), false);
  assert.equal(env.UV_CACHE_DIR, path.resolve(__dirname, "../cache/uv"));
  assert.equal(env.UV_PYTHON_INSTALL_DIR, path.resolve(__dirname, "../cache/python"));
  assert.equal(env.PYTHONHOME, "");
  assert.equal(env.PYTHONPATH, "");
});

test("uv creates the app-local venv using one managed-Python selection mechanism", () => {
  assert.deepEqual(venvArgs(), ["venv", path.resolve(__dirname, "../env"), "--python", "3.12"]);
});
