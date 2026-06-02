/**
 * 临时存储待上传的文件和需求
 * 用于首页点击启动引擎后立即跳转，在Process页面再进行API调用
 */
import { reactive } from 'vue'

const state = reactive({
  files: [],
  simulationRequirement: '',
  includeGermanSources: false,
  seedText: '',
  isPending: false
})

export function setPendingUpload(files, requirement, includeGermanSources = false, seedText = '') {
  state.files = files
  state.simulationRequirement = requirement
  state.includeGermanSources = includeGermanSources
  state.seedText = seedText
  state.isPending = true
}

export function getPendingUpload() {
  return {
    files: state.files,
    simulationRequirement: state.simulationRequirement,
    includeGermanSources: state.includeGermanSources,
    seedText: state.seedText,
    isPending: state.isPending
  }
}

export function clearPendingUpload() {
  state.files = []
  state.simulationRequirement = ''
  state.includeGermanSources = false
  state.seedText = ''
  state.isPending = false
}

export default state
