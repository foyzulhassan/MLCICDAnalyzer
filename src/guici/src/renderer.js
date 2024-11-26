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

const carouselRecommendationsNext = document.getElementById('carousel-recommendations-next')
window.addEventListener("load", async function(event) {
    // Change recommendation proposal in the mod diff model upon recommendation change
    carouselRecommendations.addEventListener('slid.bs.carousel', function(event) {
        let currentRecommendation = document.querySelector('#carousel-recommendations .carousel-inner .active .container .row button').value
        modModel.setValue(currentRecommendation)
    })

    // Add handler for loading yaml files
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