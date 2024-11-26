const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('versions', {
  node: () => process.versions.node,
  chrome: () => process.versions.chrome,
  electron: () => process.versions.electron,
  get_recommendations: (yaml) => ipcRenderer.invoke('get_recommendations', yaml),
  generate_ci: (args_dict) => ipcRenderer.invoke('generate_ci', args_dict)
})