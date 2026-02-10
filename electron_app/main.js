const { app, BrowserWindow, ipcMain } = require("electron");
const { spawn } = require("child_process");
const path = require("path");

const PYTHON_BIN =
  process.env.TUBRIC_PYTHON ||
  path.join(__dirname, "..", "tubric_kiosk", ".venv", "bin", "python");

const BACKEND_SCRIPT = path.join(
  __dirname,
  "..",
  "tubric_kiosk",
  "kiosk_backend_cli.py"
);

function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    fullscreen: true,
    kiosk: true,
    backgroundColor: "#f4f6fb",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  win.loadFile(path.join(__dirname, "index.html"));
}

ipcMain.handle("submit-checkin", async (_event, payload) => {
  return new Promise((resolve, reject) => {
    const proc = spawn(PYTHON_BIN, [BACKEND_SCRIPT], {
      stdio: ["pipe", "pipe", "pipe"],
    });

    let stdout = "";
    let stderr = "";

    proc.stdout.on("data", (d) => (stdout += d.toString()));
    proc.stderr.on("data", (d) => (stderr += d.toString()));

    proc.on("close", (code) => {
      if (code !== 0) {
        return reject(new Error(stderr || `Backend exited with code ${code}`));
      }
      try {
        resolve(JSON.parse(stdout));
      } catch (err) {
        reject(new Error(`Invalid backend response: ${err.message}`));
      }
    });

    proc.stdin.write(JSON.stringify(payload || {}));
    proc.stdin.end();
  });
});

app.whenReady().then(createWindow);

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
