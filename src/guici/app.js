const { app, BrowserWindow, ipcMain } = require('electron/main')
const { spawn } = require('node:child_process');
const path = require('node:path')
const tmp = require('tmp')
const fs = require('fs')
tmp.setGracefulCleanup();

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
  ipcMain.handle('generate_ci', async (event, ...args) => {
    return await generate_ci(args[0])
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

async function generate_ci(args_dict) {
  let command = 'python3 src/genci'
  for(arg in args_dict['files']) {
    if(args_dict['files'][arg][0] != '' && args_dict['files'][arg][0] !== undefined) {
      const tmp_file = tmp.fileSync()
      fs.appendFileSync(tmp_file.name, args_dict['files'][arg][0])
      command += ` ${arg} ${tmp_file.name}`
    }
  }
  for(arg in args_dict['misc']) {
    if(args_dict['misc'][arg][0] != '' && args_dict['misc'][arg][0] !== undefined) {
      command += ` ${arg} ${args_dict['misc'][arg].join(' ')}`
    }
  }
  command += ' --new_trace'
  
  generated_ci = '{"new": "ci"}' // TODO: replace with call to command
  return generated_ci
}