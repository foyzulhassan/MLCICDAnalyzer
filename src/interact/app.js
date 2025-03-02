const { app, BrowserWindow, ipcMain } = require('electron/main')
const { spawn } = require('node:child_process');
const path = require('node:path')
const tmp = require('tmp')
const fs = require('fs')
const { execSync } = require('child_process');
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
  win.webContents.openDevTools()
}

app.whenReady().then(() => {
  ipcMain.handle('generate_ci', async (event, ...args) => {
    return await generate_ci(args[0])
  })
  ipcMain.handle('get_initial_recommendations', async (event, ...args) => {
    return await get_initial_recommendations(args[0])
  })
  ipcMain.handle('get_recommendations', async (event, ...args) => {
    return await get_recommendations(args[0], args[1])
  })
  createWindow()
})

/**
 * Spawn a child process and return its output when it terminates
 */
async function spawnProcess(command, args_list) {
  const newProcess = spawn(command, args_list);
  return new Promise((resolve) => {
    newProcess.stdout.on('data', (data) => { resolve(data) })
    newProcess.stderr.on('data', (data) => { resolve(data) })
  })
}

/**
 * Call a python script to generate a base workflow
 */
async function generate_ci(argsDict) {
  const command = 'python3'
  const argsList = ['../genci']

  // TODO: REPLACE TEMPORARY FILE APPROACH WITH ELECTRON DIALOGS (INVOKED FROM RENDER) TO GET ABS PATHS

  for(arg in argsDict['files']) {
    if(argsDict['files'][arg][0] != '' && argsDict['files'][arg][0] !== undefined) {
      const tmp_file = tmp.fileSync()
      fs.appendFileSync(tmp_file.name, argsDict['files'][arg][0])
      argsList.push(arg)
      argsList.push(tmp_file.name)
    }
  }
  for(arg in argsDict['misc']) {
    if(argsDict['misc'][arg][0] != '' && argsDict['misc'][arg][0] !== undefined) {
      argsList.push(arg)
      argsList.push(argsDict['misc'][arg].join(' '))
    }
  }
  argsList.push('--new_trace')
  
  await spawnProcess(command, argsList)
  workflowPath = argsDict['files']['--workflow'][0]
  generatedPath = workflowPath != '' && workflowPath != undefined ? workflowPath : '../../workflow.yaml'
  generatedCi = fs.readFileSync(generatedPath).toString()
  return generatedCi
}

async function get_recommendations(workflow_name, yaml) {
  try {
    fs.writeFileSync(`../../out/${workflow_name}.recommendations.gui.current`, yaml);
    result = execSync(`python3 ../../src -a`)
    console.log(result.toString())
    const edit_actions = fs.readFileSync(`../../out/${workflow_name}.recommendations.gui`, 'utf8');
    return JSON.parse(edit_actions)
  } catch(err) {
    return null
  }
}

async function get_initial_recommendations(workflow_name) {
  try {
    fs.copyFileSync(`../../out/${workflow_name}.recommendations`, `../../out/${workflow_name}.recommendations.gui`)
    const edit_actions = fs.readFileSync(`../../out/${workflow_name}.recommendations.gui`, 'utf8');
    return JSON.parse(edit_actions)
  } catch (err) {
    return null
  }
}


  // for(i = 1; i < 4; i++) {
  //   let randomNumber = Math.floor(Math.random() * 100)
  //   recommendations.push({'description': randomNumber, 'yaml': randomNumber})
  // }