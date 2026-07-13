// Bootstrap/package contract checks for the desktop app. These are static by design:
// they catch release-path regressions without launching Electron or touching ~/.solar.
const fs = require("fs");
const path = require("path");

function read(relPath) {
  return fs.readFileSync(path.join(__dirname, relPath), "utf8");
}

function assert(name, ok, detail = "") {
  if (!ok) {
    console.error(`FAIL ${name}${detail ? `: ${detail}` : ""}`);
    process.exitCode = 1;
  } else {
    console.log(`PASS ${name}`);
  }
}

const main = read("src/main.js");
const getSolar = read("../get-solar.sh");
const releaseVersion = read("../VERSION").trim();
const app = read("../harness/status-server/react-app/src/App.tsx");
const pkg = JSON.parse(read("package.json"));
const autotest = read("autotest.sh");
const desktopWorkflow = read("../.github/workflows/desktop-build.yml");
const desktopGateJob = desktopWorkflow.split("\n  gate:\n")[1] || "";
const macResources = (pkg.build.mac.extraResources || []).map((entry) => entry.to);

assert(
  "fresh packaged app syncs bundled harness before network installer",
  main.includes("!runtimeInstalled()") &&
    main.includes("SOLAR_DESKTOP_ALLOW_DEV_RUNTIME_SYNC") &&
    main.includes("install action: using bundled harness before network installer"),
);

assert(
  "symlinked ~/.solar/harness is rejected before sync/start",
  main.includes("runtimeSymlinkIssue") &&
    main.includes("runtime-symlink") &&
    main.includes("refusing bundled harness sync into symlinked runtime"),
);

assert(
  "stale runtime pid/port/token markers are cleared before start",
  main.includes("clearRuntimeStateMarkers") &&
    main.includes("status-server.pid") &&
    main.includes("status-server.port"),
);

assert(
  "macOS bundled sync installs LaunchAgent",
  main.includes("installMacLaunchAgent") &&
    main.includes("com.solar.status-server.plist") &&
    main.includes("launchctl"),
);

assert(
  "mac package carries LaunchAgent helper resources",
  macResources.includes("runtime/install-macos-agent.sh") &&
    macResources.includes("runtime/uninstall-macos-agent.sh") &&
    macResources.includes("runtime/com.solar.status-server.plist"),
);

assert(
  "get-solar fallback defaults to the package release channel",
  getSolar.includes(`SOLAR_CHANNEL="\${SOLAR_CHANNEL:-v${releaseVersion}}"`),
);

assert(
  "session UI has an error boundary fallback",
  app.includes("class AppErrorBoundary") &&
    app.includes("componentDidCatch") &&
    app.includes("Session view could not render"),
);

assert(
  "desktop persists renderer/runtime diagnostics to log file",
  main.includes("appendDesktopLog") &&
    main.includes("desktop.log") &&
    main.includes("renderer-process-gone") &&
    main.includes("window-unresponsive"),
);

assert(
  "desktop autotest runs this bootstrap/package contract",
  autotest.includes("node bootstrap-contract.test.js"),
);

assert(
  "desktop artifacts wait for the gate before building",
  /\n  build:\n    needs: gate\n/.test(desktopWorkflow),
);

assert(
  "desktop tag gate runs release coherence before packaging",
  desktopGateJob.includes("bash scripts/check-release-coherence.sh"),
);
