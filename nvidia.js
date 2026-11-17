const { shell, stop } = require("./launcher");
module.exports = { run: [stop(), shell("install --backend nvidia")] };
