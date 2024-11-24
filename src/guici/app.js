const { app, BrowserWindow, ipcMain } = require('electron/main')
const path = require('node:path')

const createWindow = () => {
  const win = new BrowserWindow({
    width: 1600,
    height: 900,
    autoHideMenuBar: false,
    webPreferences: {
      preload: path.join(__dirname, 'src/preload.js'),
      worldSafeExecuteJavaScript: true
    }
  })
  win.loadFile('public/index.html')
}
app.whenReady().then(() => {
  ipcMain.handle('ping', () => 'pong')
  createWindow()
})