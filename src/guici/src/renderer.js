// Add YAML Diff Editor to Page
let orgModel = null
let modModel = null
let diffEditor = null

require.config({ paths: { vs: '../node_modules/monaco-editor/min/vs' } })
require(['vs/editor/editor.main'], function () {
    const yamlEditor = document.getElementById('yaml-editor')
    orgModel = monaco.editor.createModel('', 'text')
    modModel = monaco.editor.createModel('', 'text')
    diffEditor = monaco.editor.createDiffEditor(yamlEditor, { automaticLayout: true, readOnly: true })
    diffEditor.setModel({original: orgModel, modified: modModel})
})

// Add Recommendations to Carousel on Page
const carouselRecommendations = document.getElementById('carousel-recommendations')
const carouselRecommendationsInner = document.querySelector('#carousel-recommendations .carousel-inner')
async function get_recommendations(yaml) {
    // Add recommendations to page
    const recommendations = await window.versions.get_recommendations(yaml)
    carouselRecommendationsInner.innerHTML = ''
    recommendations.forEach(recommendation => {
        carouselRecommendationsInner.innerHTML += `
        <div class="carousel-item">
            <div class="container">
                <div class="row">
                    <div class="col-10"><div class="d-flex h-100 align-items-center justify-content-center">${recommendation['description']}</div></div>
                    <button class="apply-recommendation-btn col-2 btn btn-outline-dark" value="${recommendation['yaml']}">Apply</button>
                </div>
            </div>
        </div>`
    })
    carouselRecommendationsInner.firstElementChild?.classList.add('active')

    // Set up apply recommendation handlers
    const applyBtns = document.getElementsByClassName('apply-recommendation-btn')
    for(i = 0; i < applyBtns.length; i++) {
        applyBtns[i].addEventListener("click", async function(event) {
            let currentRecommendation = document.querySelector('#carousel-recommendations .carousel-inner .active .container .row button').value
            orgModel.setValue(currentRecommendation)
            await get_recommendations(yaml)
            carouselRecommendationsNext.click()
        })
    }
}

async function readFile(file) {
    return new Promise((resolve) => {
        if(file instanceof File) {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result);
            reader.readAsText(file);
        } else {
            resolve('')
        }
    });
}

const carouselRecommendationsNext = document.getElementById('carousel-recommendations-next')
window.addEventListener("load", async function(event) {
    // Change recommendation proposal in the mod diff model upon recommendation change
    carouselRecommendations.addEventListener('slid.bs.carousel', function(event) {
        let currentRecommendation = document.querySelector('#carousel-recommendations .carousel-inner .active .container .row button').value
        modModel.setValue(currentRecommendation)
    })

    // Add handlers for creating new yaml files
    const newTargetFileOrDirectory = document.getElementById('input-group-target-file')
    const newLlmAugmentSwitch = document.getElementById('input-group-newllmaugment-switch')
    const newLlmApiKeyInput = document.getElementById('input-group-newllmaugment-text')
    const newWorkflowNameInput = document.getElementById('input-group-workflowname-text')
    const newHostContainerInput = document.getElementById('input-group-hostcontainer-text')
    const newRequirementFileInput = document.getElementById('input-group-requirements-file')
    const newWorkflowFileInput = document.getElementById('input-group-workflow-file')
    const newTracelogFileInput = document.getElementById('input-group-tracelog-file')
    const newPathlogFileInput = document.getElementById('input-group-pathslog-file')
    const newDockerlogFileInput = document.getElementById('input-group-dockerlog-file')
    const newCloseBtn = document.getElementById('new-close-btn')
    const newGenerateBtn = document.getElementById('new-yaml-btn')
    const newYamlStatus = document.getElementById('new-status-text')
    newGenerateBtn.addEventListener('click', async function(event) {
        newYamlStatus.innerText = ''

        if(newTargetFileOrDirectory.files[0] === undefined 
            || newWorkflowNameInput.value.trim() == '' 
            || newLlmAugmentSwitch.getAttribute('aria-expanded') && newLlmApiKeyInput.value.trim() == '') {
            newYamlStatus.innerText = '* Please fill out all required fields'
            return
        }

        const hostContainer = newHostContainerInput.value
        const llmApiKey = newLlmApiKeyInput.value
        const workflowName = newWorkflowNameInput.value
        const targetFile = newTargetFileOrDirectory.files[0]
        const requirementFile = newRequirementFileInput.files[0]
        const workflowFile = newWorkflowFileInput.files[0]
        const tracelogFile = newTracelogFileInput.files[0]
        const pathlogFile = newPathlogFileInput.files[0]
        const dockerlogFile = newDockerlogFileInput.files[0]
        const args_dict = {
            'files': {
                '--target': [],
                '--requirements': [],
                '--workflow': [],
                '--trace_log': [],
                '--paths_log': [],
                '--docker_log': []
            }, 
            'misc': {
                '--llm_api_key': [llmApiKey],
                '--workflow_name': [workflowName],
                '--host_container': [hostContainer]
            }
        }
        args_dict['files']['--target'].push(await readFile(targetFile))
        args_dict['files']['--requirements'].push(await readFile(requirementFile))
        args_dict['files']['--workflow'].push(await readFile(workflowFile))
        args_dict['files']['--trace_log'].push(await readFile(tracelogFile))
        args_dict['files']['--paths_log'].push(await readFile(pathlogFile))
        args_dict['files']['--docker_log'].push(await readFile(dockerlogFile))
        
        generated_ci = await window.versions.generate_ci(args_dict)
        orgModel.setValue(generated_ci)
        await get_recommendations('')
        carouselRecommendationsNext.click()
        newCloseBtn.click()
    })

    // Add handlers for loading yaml files
    const loadYamlBtn = document.getElementById('load-yaml-btn')
    const loadYamlFileInput = document.getElementById('input-group-loadyaml-file')
    const loadYamlLlmSwitch = document.getElementById('input-group-loadllmaugment-switch')
    const loadYamlApiKey = document.getElementById('input-group-loadapikey-input')
    const loadYamlStatus = document.getElementById('input-group-loadstatus-text')
    const loadYamlCloseBtn = this.document.getElementById('load-close-btn')
    loadYamlBtn.addEventListener('click', async function(event) {
        loadYamlStatus.innerText = ''
        if(loadYamlFileInput.files[0] === undefined || loadYamlLlmSwitch.getAttribute('aria-expanded') && loadYamlApiKey.value.trim() == '') {
            loadYamlStatus.innerText = '* Please fill out all required fields'
            return
        }

        const selectedFile = loadYamlFileInput.files[0]
        const reader = new FileReader()
        reader.onload = () => orgModel.setValue(reader.result.trim())
        reader.readAsText(selectedFile)
        await get_recommendations('')
        carouselRecommendationsNext.click()
        loadYamlCloseBtn.click()
    })
});