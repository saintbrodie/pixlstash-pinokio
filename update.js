const { shell, stop } = require("./launcher");
module.exports = {
  run: [
    stop(),
    shell("update-code"),
    { method: "script.start", params: { uri: "install.js" } }
  ]
};
