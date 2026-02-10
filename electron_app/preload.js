const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("tubric", {
  submitCheckin: (payload) => ipcRenderer.invoke("submit-checkin", payload),
});
