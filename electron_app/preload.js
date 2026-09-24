const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("tubric", {
  lookup: (payload) => ipcRenderer.invoke("lookup-checkin", payload),
  submitCheckin: (payload) => ipcRenderer.invoke("submit-checkin", payload),
});
