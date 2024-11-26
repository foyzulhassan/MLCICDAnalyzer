const { app, BrowserWindow, ipcMain } = require('electron/main')
const { spawn } = require('node:child_process');
const path = require('node:path')

const createWindow = () => {
  const win = new BrowserWindow({
    width: 1600,
    height: 900,
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'src/preload.js'),
      worldSafeExecuteJavaScript: true
    }
  })
  win.loadFile('public/index.html')
}

app.whenReady().then(() => {
  ipcMain.handle('get_recommendations', get_recommendations)
  createWindow()
})

function get_recommendations() {
  return [{'description': 1, 'yaml': 'one'}, {'description': 2, 'yaml': 'two'}, {'description': 3, 'yaml': 'three'}] // replace with bash call
}