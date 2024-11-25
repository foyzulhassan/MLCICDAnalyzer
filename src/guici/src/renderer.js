// const func = async () => {
//     const response = await window.versions.ping()
// }
// func()

// import { editor } from 'monaco-editor'

require.config({ paths: { vs: '../node_modules/monaco-editor/min/vs' } });
require(['vs/editor/editor.main'], function () {
    const yamlEditor = document.getElementById('yaml-editor')
    const orgModel =  monaco.editor.createModel('{ "key": "value" }', 'text')
    const modModel =  monaco.editor.createModel('{ "key": "valu" }', 'text')
    const diffEditor = monaco.editor.createDiffEditor(yamlEditor, { automaticLayout: true })
    diffEditor.setModel({original: orgModel, modified: modModel})
});


// const mainModal = document.getElementById('main-modal')
// document.getElementById('nav-item-new').onclick((e) => {
//     mainModal.showPopover()
// });

// myModal.addEventListener('shown.bs.modal', () => {
//   myInput.focus()
// })
