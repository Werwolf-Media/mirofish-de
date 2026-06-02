<template>
  <div class="wizard-overlay" @click.self="close">
    <div class="wizard-modal">
      <header class="wizard-header">
        <div class="wizard-title">
          <img :src="werwolfLogo" alt="Werwolf Media" class="wizard-logo" />
          <span>{{ $t('onboarding.title') }}</span>
        </div>
        <button class="wizard-close" @click="close" aria-label="close">×</button>
      </header>

      <div class="wizard-progress">
        <div class="wizard-progress-bar" :style="{ width: progressPct + '%' }"></div>
      </div>
      <div class="wizard-stepinfo">{{ $t('onboarding.stepOf', { current: step, total: TOTAL }) }}</div>

      <div class="wizard-body">
        <!-- Schritt 1: Vorlage -->
        <div v-if="step === 1" class="wstep">
          <h2 class="wstep-title">{{ $t('onboarding.step1Title') }}</h2>
          <p class="wstep-sub">{{ $t('onboarding.step1Subtitle') }}</p>
          <div class="template-grid">
            <button
              v-for="tpl in templates"
              :key="tpl.key"
              class="template-card"
              :class="{ selected: selectedTemplate === tpl.key }"
              @click="applyTemplate(tpl)"
            >
              <span class="template-card-title">{{ $t(tpl.titleKey) }}</span>
              <span class="template-card-desc">{{ $t(tpl.descKey) }}</span>
            </button>
          </div>
        </div>

        <!-- Schritt 2: Frage & Gegenstand -->
        <div v-else-if="step === 2" class="wstep">
          <h2 class="wstep-title">{{ $t('onboarding.step2Title') }}</h2>
          <label class="wfield">
            <span class="wlabel">{{ $t('onboarding.questionLabel') }} <em>*</em></span>
            <span class="whint">{{ $t('onboarding.questionHint') }}</span>
            <textarea v-model="form.question" rows="2" :placeholder="$t('onboarding.questionPlaceholder')"></textarea>
          </label>
          <label class="wfield">
            <span class="wlabel">{{ $t('onboarding.subjectLabel') }}</span>
            <span class="whint">{{ $t('onboarding.subjectHint') }}</span>
            <textarea v-model="form.subject" rows="3" :placeholder="$t('onboarding.subjectPlaceholder')"></textarea>
          </label>
        </div>

        <!-- Schritt 3: Zielgruppe & Zeitraum -->
        <div v-else-if="step === 3" class="wstep">
          <h2 class="wstep-title">{{ $t('onboarding.step3Title') }}</h2>
          <label class="wfield">
            <span class="wlabel">{{ $t('onboarding.audienceLabel') }}</span>
            <span class="whint">{{ $t('onboarding.audienceHint') }}</span>
            <input v-model="form.audience" type="text" :placeholder="$t('onboarding.audiencePlaceholder')" />
          </label>
          <label class="wfield">
            <span class="wlabel">{{ $t('onboarding.timeframeLabel') }}</span>
            <span class="whint">{{ $t('onboarding.timeframeHint') }}</span>
            <input v-model="form.timeframe" type="text" :placeholder="$t('onboarding.timeframePlaceholder')" />
          </label>
        </div>

        <!-- Schritt 4: Variablen & Material -->
        <div v-else-if="step === 4" class="wstep">
          <h2 class="wstep-title">{{ $t('onboarding.step4Title') }}</h2>
          <div class="wfield">
            <span class="wlabel">{{ $t('onboarding.variablesLabel') }}</span>
            <span class="whint">{{ $t('onboarding.variablesHint') }}</span>
            <div v-for="(v, idx) in form.variables" :key="idx" class="var-row">
              <input v-model="form.variables[idx]" type="text" :placeholder="$t('onboarding.variablesPlaceholder')" />
              <button class="var-remove" @click="removeVariable(idx)" :aria-label="$t('onboarding.removeVariable')">×</button>
            </div>
            <button class="var-add" @click="addVariable">+ {{ $t('onboarding.addVariable') }}</button>
          </div>

          <div class="wfield">
            <span class="wlabel">{{ $t('onboarding.materialLabel') }}</span>
            <span class="whint">{{ $t('onboarding.materialHint') }}</span>
            <div
              class="wupload"
              :class="{ 'drag-over': isDragOver }"
              @dragover.prevent="isDragOver = true"
              @dragleave.prevent="isDragOver = false"
              @drop.prevent="onDrop"
              @click="triggerFileInput"
            >
              <input ref="fileInput" type="file" multiple accept=".pdf,.md,.txt" style="display:none" @change="onFileSelect" />
              <template v-if="form.files.length === 0">
                <span class="wupload-icon">↑</span>
                <span>{{ $t('onboarding.uploadHint') }}</span>
              </template>
              <div v-else class="wfile-list">
                <div v-for="(f, i) in form.files" :key="i" class="wfile-item">
                  <span class="wfile-name">📄 {{ f.name }}</span>
                  <button class="wfile-remove" @click.stop="removeFile(i)">×</button>
                </div>
              </div>
            </div>

            <label class="wsource-optin">
              <input type="checkbox" v-model="form.includeGermanSources" />
              <span>
                <span class="wsource-label">{{ $t('home.germanSourcesLabel') }}</span>
                <span class="wsource-hint">{{ $t('home.germanSourcesHint') }}</span>
              </span>
            </label>
          </div>
        </div>

        <!-- Schritt 5: Überblick & Start -->
        <div v-else-if="step === 5" class="wstep">
          <h2 class="wstep-title">{{ $t('onboarding.step5Title') }}</h2>
          <p class="wstep-sub">{{ $t('onboarding.reviewHint') }}</p>
          <label class="wfield">
            <span class="wlabel">{{ $t('onboarding.generatedPrompt') }}</span>
            <textarea v-model="editablePrompt" rows="12" class="wreview"></textarea>
          </label>
          <p v-if="!form.question.trim()" class="werror">{{ $t('onboarding.missingQuestion') }}</p>
        </div>
      </div>

      <footer class="wizard-footer">
        <button v-if="step > 1" class="wbtn-ghost" @click="prev">{{ $t('onboarding.back') }}</button>
        <div class="wizard-spacer"></div>
        <button class="wbtn-ghost" @click="close">{{ $t('onboarding.cancel') }}</button>
        <button v-if="step < TOTAL" class="wbtn-primary" :disabled="!canNext" @click="next">{{ $t('onboarding.next') }}</button>
        <button v-else class="wbtn-primary" :disabled="!canStart" @click="submit">{{ $t('onboarding.start') }}</button>
      </footer>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import werwolfLogo from '../assets/logo/werwolf-icon.svg'

const { t } = useI18n()
const emit = defineEmits(['close', 'submit'])

const TOTAL = 5
const step = ref(1)
const isDragOver = ref(false)
const fileInput = ref(null)
const editablePrompt = ref('')
const selectedTemplate = ref(null)

const form = reactive({
  question: '',
  subject: '',
  audience: '',
  timeframe: '',
  variables: [''],
  files: [],
  includeGermanSources: false
})

const templates = [
  {
    key: 'blank', titleKey: 'onboarding.templateBlank', descKey: 'onboarding.templateBlankDesc',
    prefill: null
  },
  {
    key: 'product', titleKey: 'onboarding.tplProductTitle', descKey: 'onboarding.tplProductDesc',
    prefill: {
      question: 'Wie reagiert die Öffentlichkeit auf die Markteinführung in den ersten Wochen?',
      subject: 'Markteinführung eines neuen Produkts oder Service auf dem deutschen Markt',
      audience: 'deutsche Verbraucher der relevanten Zielgruppe',
      timeframe: 'die ersten 4 Wochen',
      variables: ['Rabattaktion in den ersten Wochen', 'kritischer Testbericht eines großen Mediums']
    }
  },
  {
    key: 'policy', titleKey: 'onboarding.tplPolicyTitle', descKey: 'onboarding.tplPolicyDesc',
    prefill: {
      question: 'Wie entwickelt sich die öffentliche und politische Debatte?',
      subject: 'Neuer Gesetzentwurf bzw. politische Maßnahme in Deutschland',
      audience: 'betroffene Bevölkerungsgruppen, Verbände und Opposition',
      timeframe: 'die ersten 6 Wochen',
      variables: ['nachträgliche Anhebung der Förderhöhe', 'mediale Talkshow zum Thema']
    }
  },
  {
    key: 'local', titleKey: 'onboarding.tplLocalTitle', descKey: 'onboarding.tplLocalDesc',
    prefill: {
      question: 'Wie reagieren Bürger und Einzelhändler auf die geplante Maßnahme?',
      subject: 'Lokale Maßnahme (z. B. Verkehrsberuhigung oder Stadtprojekt)',
      audience: 'Bürger, Einzelhändler und Pendler einer mittelgroßen Stadt',
      timeframe: 'die ersten 8 Wochen',
      variables: ['kostenlose ÖPNV-Aktion', 'negative Berichterstattung in Woche 1']
    }
  }
]

const progressPct = computed(() => Math.round((step.value / TOTAL) * 100))

const canNext = computed(() => {
  if (step.value === 2) return form.question.trim() !== ''
  return true
})
const canStart = computed(() => form.question.trim() !== '')

const applyTemplate = (tpl) => {
  selectedTemplate.value = tpl.key
  if (tpl.prefill) {
    form.question = tpl.prefill.question
    form.subject = tpl.prefill.subject
    form.audience = tpl.prefill.audience
    form.timeframe = tpl.prefill.timeframe
    form.variables = [...tpl.prefill.variables, '']
  }
  step.value = 2
}

const addVariable = () => form.variables.push('')
const removeVariable = (idx) => {
  form.variables.splice(idx, 1)
  if (form.variables.length === 0) form.variables.push('')
}

const triggerFileInput = () => fileInput.value?.click()
const filterFiles = (list) => Array.from(list).filter(f => ['pdf', 'md', 'txt'].includes(f.name.split('.').pop().toLowerCase()))
const onFileSelect = (e) => { form.files.push(...filterFiles(e.target.files)) }
const onDrop = (e) => { isDragOver.value = false; form.files.push(...filterFiles(e.dataTransfer.files)) }
const removeFile = (i) => form.files.splice(i, 1)

const buildPrompt = () => {
  const lines = []
  if (form.question.trim()) lines.push(`${t('onboarding.promptQuestion')}: ${form.question.trim()}`)
  if (form.subject.trim()) lines.push(`${t('onboarding.promptSubject')}: ${form.subject.trim()}`)
  if (form.audience.trim()) lines.push(`${t('onboarding.promptAudience')}: ${form.audience.trim()}`)
  if (form.timeframe.trim()) lines.push(`${t('onboarding.promptTimeframe')}: ${form.timeframe.trim()}`)
  const vars = form.variables.map(v => v.trim()).filter(Boolean)
  if (vars.length) {
    lines.push(`${t('onboarding.promptVariables')}:`)
    vars.forEach(v => lines.push(`- ${v}`))
  }
  lines.push('')
  lines.push(t('onboarding.promptInstruction'))
  return lines.join('\n')
}

const next = () => {
  if (!canNext.value) return
  if (step.value === TOTAL - 1) {
    editablePrompt.value = buildPrompt()
  }
  step.value = Math.min(step.value + 1, TOTAL)
}
const prev = () => { step.value = Math.max(step.value - 1, 1) }
const close = () => emit('close')

const submit = () => {
  if (!canStart.value) return
  const requirement = editablePrompt.value.trim() || buildPrompt()
  emit('submit', {
    files: form.files,
    requirement,
    seedText: requirement,
    includeGermanSources: form.includeGermanSources
  })
}
</script>

<style scoped>
.wizard-overlay {
  position: fixed;
  inset: 0;
  z-index: 9000;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.wizard-modal {
  width: 100%;
  max-width: 640px;
  max-height: 90vh;
  background: #ffffff;
  border-radius: 14px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  font-family: 'JetBrains Mono', 'Space Grotesk', -apple-system, sans-serif;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.wizard-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  background: #000;
  color: #fff;
}

.wizard-title { display: flex; align-items: center; gap: 10px; font-weight: 700; letter-spacing: 0.5px; }
.wizard-logo { height: 22px; width: auto; filter: brightness(0) invert(1); }
.wizard-close { background: none; border: none; color: #fff; font-size: 24px; line-height: 1; cursor: pointer; opacity: 0.7; }
.wizard-close:hover { opacity: 1; }

.wizard-progress { height: 4px; background: #eee; }
.wizard-progress-bar { height: 100%; background: #ff6b2c; transition: width 0.3s ease; }
.wizard-stepinfo { padding: 10px 20px 0; font-size: 0.72rem; color: #999; letter-spacing: 0.5px; }

.wizard-body { padding: 12px 20px 20px; overflow-y: auto; flex: 1; }
.wstep-title { font-size: 1.15rem; font-weight: 700; margin: 6px 0 4px; }
.wstep-sub { font-size: 0.85rem; color: #777; margin-bottom: 16px; line-height: 1.4; }

.template-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.template-card {
  display: flex; flex-direction: column; gap: 4px; text-align: left;
  padding: 16px; border: 1.5px solid #e3e3e3; border-radius: 10px; background: #fafafa; cursor: pointer; transition: all 0.15s;
}
.template-card:hover { border-color: #ff6b2c; background: #fff7f2; }
.template-card.selected { border-color: #ff6b2c; background: #fff4ee; }
.template-card-title { font-weight: 700; font-size: 0.95rem; }
.template-card-desc { font-size: 0.78rem; color: #888; line-height: 1.35; }

.wfield { display: flex; flex-direction: column; gap: 4px; margin-bottom: 18px; }
.wlabel { font-weight: 600; font-size: 0.9rem; }
.wlabel em { color: #ff6b2c; font-style: normal; }
.whint { font-size: 0.76rem; color: #999; line-height: 1.35; margin-bottom: 4px; }
.wfield input[type="text"], .wfield textarea, .wreview {
  width: 100%; padding: 10px 12px; border: 1.5px solid #e0e0e0; border-radius: 8px;
  font-family: inherit; font-size: 0.9rem; resize: vertical; outline: none; transition: border-color 0.15s;
}
.wfield input:focus, .wfield textarea:focus, .wreview:focus { border-color: #ff6b2c; }
.wreview { line-height: 1.55; }

.var-row { display: flex; gap: 8px; margin-bottom: 8px; }
.var-row input { flex: 1; }
.var-remove { width: 36px; border: 1.5px solid #e0e0e0; background: #fafafa; border-radius: 8px; cursor: pointer; font-size: 18px; color: #999; }
.var-remove:hover { border-color: #ff6b2c; color: #ff6b2c; }
.var-add { margin-top: 2px; align-self: flex-start; background: none; border: none; color: #ff6b2c; font-weight: 600; font-size: 0.85rem; cursor: pointer; font-family: inherit; }

.wupload {
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px;
  padding: 22px; border: 1.5px dashed #ccc; border-radius: 10px; background: #fafafa; cursor: pointer; color: #888; font-size: 0.85rem; text-align: center;
}
.wupload.drag-over { border-color: #ff6b2c; background: #fff7f2; }
.wupload-icon { font-size: 20px; }
.wfile-list { width: 100%; display: flex; flex-direction: column; gap: 6px; }
.wfile-item { display: flex; align-items: center; justify-content: space-between; background: #fff; border: 1px solid #eee; border-radius: 6px; padding: 6px 10px; }
.wfile-name { font-size: 0.82rem; color: #333; }
.wfile-remove { background: none; border: none; color: #999; font-size: 16px; cursor: pointer; }

.wsource-optin { display: flex; align-items: flex-start; gap: 10px; margin-top: 14px; cursor: pointer; }
.wsource-optin input { margin-top: 3px; width: 16px; height: 16px; accent-color: #ff6b2c; }
.wsource-label { display: block; font-weight: 600; font-size: 0.85rem; }
.wsource-hint { display: block; font-size: 0.74rem; color: #999; line-height: 1.3; }

.werror { color: #d9480f; font-size: 0.8rem; margin-top: 8px; }

.wizard-footer { display: flex; align-items: center; gap: 10px; padding: 14px 20px; border-top: 1px solid #eee; background: #fafafa; }
.wizard-spacer { flex: 1; }
.wbtn-ghost { background: none; border: 1px solid #ddd; border-radius: 8px; padding: 9px 16px; font-family: inherit; font-size: 0.85rem; font-weight: 500; cursor: pointer; color: #555; }
.wbtn-ghost:hover { border-color: #999; }
.wbtn-primary { background: #ff6b2c; color: #fff; border: none; border-radius: 8px; padding: 10px 20px; font-family: inherit; font-size: 0.88rem; font-weight: 700; cursor: pointer; }
.wbtn-primary:hover:not(:disabled) { opacity: 0.92; }
.wbtn-primary:disabled { opacity: 0.45; cursor: not-allowed; }
</style>
