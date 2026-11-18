module.exports = {
  version: "3.0",
  title: "PixlStash",
  description: "Self-hosted image manager for photographers and AI creators. Search by meaning, tag and caption images, train LoRAs from your library, and run ComfyUI workflows.",
  icon: "icon.svg",
  requires: [{ name: "node" }, { name: "uv" }],
  menu: async (kernel, info) => {
    for (const script of ["install.js", "update.js", "nvidia.js", "cpu.js", "stop.js"]) {
      if (info.running(script)) return [{ icon: "fa-solid fa-spinner", text: "Working — view progress", href: script }];
    }
    if (info.running("start.js")) {
      const local = info.local("start.js");
      const stop = { icon: "fa-solid fa-stop", text: "Stop", href: "stop.js" };
      if (!local?.url) return [
        { icon: "fa-solid fa-spinner", text: "Starting PixlStash — view progress", href: "start.js" },
        stop
      ];
      return [
        { icon: "fa-solid fa-globe", text: "Open WebUI", href: local.url, popout: true },
        { icon: "fa-solid fa-terminal", text: "Server Log", href: "start.js" },
        stop
      ];
    }
    if (!info.exists("env/pixlstash-installed.json")) return [
      { icon: "fa-solid fa-download", text: "Install PixlStash (CPU)", href: "install.js" },
      { icon: "fa-solid fa-microchip", text: "Install PixlStash (NVIDIA CUDA 13)", href: "nvidia.js" }
    ];
    return [
      { icon: "fa-solid fa-play", text: "Start", href: "start.js" },
      { icon: "fa-solid fa-rotate", text: "Update", href: "update.js" },
      { icon: "fa-solid fa-microchip", text: "Enable NVIDIA (CUDA 13)", href: "nvidia.js" },
      { icon: "fa-solid fa-desktop", text: "Use CPU / repair installation", href: "cpu.js" }
    ];
  }
};
