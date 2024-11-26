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
  ipcMain.handle('get_recommendations', async (event, ...args) => {
    return await get_recommendations(args[0])
  })
  createWindow()
})

async function get_recommendations(yaml) {
  // TODO: replace with bash call
  const recommendations = []
  for(i = 1; i < 4; i++) {
    let randomNumber = Math.floor(Math.random() * 100)
    recommendations.push({'description': randomNumber, 'yaml': randomNumber})
  }
  return recommendations
}