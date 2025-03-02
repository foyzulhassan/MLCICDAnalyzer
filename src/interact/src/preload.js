const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('versions', {
  node: () => process.versions.node,
  chrome: () => process.versions.chrome,
  electron: () => process.versions.electron,
  generate_ci: (args_dict) => ipcRenderer.invoke('generate_ci', args_dict),
  get_initial_recommendations: (workflow_name) => ipcRenderer.invoke('get_initial_recommendations', workflow_name),
  get_recommendations: (workflow_name, yaml) => ipcRenderer.invoke('get_recommendations', workflow_name, yaml)
})