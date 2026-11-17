module.exports = {
  version: "3.0",
  title: "PixlStash",
  description: "Local image library with AI tagging, search and ComfyUI integration. CPU by default; optional NVIDIA acceleration.",
  icon: "icon.svg",
  requires: [{ name: "node" }, { name: "uv" }],
  menu: async (kernel, info) => {
    for (const script of ["install.js", "update.js", "nvidia.js", "cpu.js", "stop.js"]) {
      if (info.running(script)) return [{ default: true, icon: "fa-solid fa-spinner", text: "Working — view progress", href: script }];
    }
    if (info.running("start.js")) {
      const local = info.local("start.js");
      const stop = { icon: "fa-solid fa-stop", text: "Stop", href: "stop.js" };
      if (!local?.url) return [
        { default: true, icon: "fa-solid fa-spinner", text: "Starting PixlStash — view progress", href: "start.js" },
        stop
      ];
      return [
        { default: true, icon: "fa-solid fa-globe", text: "Open WebUI", href: local.url },
        { icon: "fa-solid fa-terminal", text: "Server Log", href: "start.js" },
        stop
      ];
    }
    if (!info.exists("env/pixlstash-installed.json")) return [
      { default: true, icon: "fa-solid fa-download", text: "Install PixlStash (CPU)", href: "install.js" }
    ];
    return [
      { default: true, icon: "fa-solid fa-play", text: "Start", href: "start.js" },
      { icon: "fa-solid fa-rotate", text: "Update", href: "update.js" },
      { icon: "fa-solid fa-microchip", text: "Enable NVIDIA (CUDA 13)", href: "nvidia.js" },
      { icon: "fa-solid fa-desktop", text: "Use CPU / repair installation", href: "cpu.js" }
    ];
  }
};
