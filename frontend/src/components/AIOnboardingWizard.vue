<template>
  <div class="wizard-overlay" @click.self="close">
    <div class="wizard-modal">
      <header class="wizard-header">
        <div class="wizard-title">
          <img :src="werwolfLogo" alt="Werwolf Media" class="wizard-logo" />
          <span>{{ $t('aiOnboarding.title') }}</span>
        </div>
        <button class="wizard-close" @click="close" aria-label="close">×</button>
      </header>

      <!-- CHAT-PHASE -->
      <template v-if="phase === 'chat'">
        <div class="chat-area" ref="chatArea">
          <div v-for="(m, i) in messages" :key="i" class="chat-msg" :class="m.role">
            <div class="chat-avatar">{{ m.role === 'user' ? 'D' : 'KI' }}</div>
            <div class="chat-bubble" v-html="renderMarkdown(m.content)"></div>
          </div>
          <div v-if="isSending" class="chat-msg assistant">
            <div class="chat-avatar">KI</div>
            <div class="chat-bubble typing">{{ $t('aiOnboarding.thinking') }}</div>
          </div>
        </div>

        <div v-if="docName" class="doc-chip">📄 {{ docName }} <button @click="removeDoc">×</button></div>
        <p v-if="errorMsg" class="werror">{{ errorMsg }}</p>

        <footer class="chat-footer">
          <input ref="docInput" type="file" accept=".pdf,.md,.txt" style="display:none" @change="onDocSelect" />
          <button class="attach-btn" @click="triggerDoc" :disabled="isSending" :title="$t('aiOnboarding.attachDoc')">📎</button>
          <textarea
            v-model="input"
            class="chat-input"
            rows="1"
            :placeholder="$t('aiOnboarding.inputPlaceholder')"
            :disabled="isSending"
            @keydown.enter.exact.prevent="sendMessage"
          ></textarea>
          <button class="send-btn" @click="sendMessage" :disabled="isSending || !input.trim()">
            {{ $t('aiOnboarding.send') }}
          </button>
        </footer>
      </template>

      <!-- REVIEW-PHASE -->
      <template v-else>
        <div class="review-area">
          <h2 class="review-title">{{ $t('aiOnboarding.reviewTitle') }}</h2>
          <label class="rfield">
            <span class="rlabel">{{ $t('aiOnboarding.requirementLabel') }}</span>
            <textarea v-model="editableRequirement" rows="6"></textarea>
          </label>
          <label class="rfield">
            <span class="rlabel">{{ $t('aiOnboarding.seedTextLabel') }}</span>
            <textarea v-model="editableSeedText" rows="9"></textarea>
          </label>

          <label class="rsource-optin">
            <input type="checkbox" v-model="includeGermanSources" />
            <span>
              <span class="rsource-label">{{ $t('home.germanSourcesLabel') }}</span>
              <span class="rsource-hint">{{ $t('home.germanSourcesHint') }}</span>
            </span>
          </label>

          <div class="rfield">
            <span class="rlabel">{{ $t('aiOnboarding.materialLabel') }}</span>
            <div class="rfiles" v-if="files.length">
              <div v-for="(f, i) in files" :key="i" class="rfile">📄 {{ f.name }} <button @click="removeFile(i)">×</button></div>
            </div>
            <button class="attach-line" @click="triggerReviewDoc">+ {{ $t('aiOnboarding.uploadHint') }}</button>
            <input ref="reviewDocInput" type="file" accept=".pdf,.md,.txt" style="display:none" @change="onReviewDocSelect" />
          </div>
        </div>

        <footer class="review-footer">
          <button class="wbtn-ghost" @click="phase = 'chat'">{{ $t('aiOnboarding.backToChat') }}</button>
          <div class="wizard-spacer"></div>
          <button class="wbtn-primary" :disabled="!editableRequirement.trim()" @click="start">{{ $t('aiOnboarding.start') }}</button>
        </footer>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import werwolfLogo from '../assets/logo/werwolf-icon.svg'
import { chatWizard, extractWizardDoc } from '../api/wizard'

const { t } = useI18n()
const emit = defineEmits(['close', 'submit'])

const messages = ref([])
const input = ref('')
const isSending = ref(false)
const phase = ref('chat')
const editableRequirement = ref('')
const editableSeedText = ref('')
const files = ref([])
const documentText = ref('')
const docName = ref('')
const includeGermanSources = ref(false)
const errorMsg = ref('')

const chatArea = ref(null)
const docInput = ref(null)
const reviewDocInput = ref(null)

onMounted(() => {
  messages.value.push({ role: 'assistant', content: t('aiOnboarding.greeting') })
})

const renderMarkdown = (text) => {
  const esc = String(text || '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  return esc
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>')
}

const scrollDown = () => {
  nextTick(() => { if (chatArea.value) chatArea.value.scrollTop = chatArea.value.scrollHeight })
}

const sendMessage = async () => {
  const text = input.value.trim()
  if (!text || isSending.value) return
  errorMsg.value = ''
  messages.value.push({ role: 'user', content: text })
  input.value = ''
  isSending.value = true
  scrollDown()
  try {
    const res = await chatWizard(messages.value, documentText.value)
    const data = res.data || {}
    if (data.reply) messages.value.push({ role: 'assistant', content: data.reply })
    if (data.status === 'ready') {
      editableRequirement.value = data.simulationRequirement || ''
      editableSeedText.value = data.seedText || ''
      phase.value = 'review'
    }
  } catch (e) {
    errorMsg.value = (e && e.message) ? e.message : t('aiOnboarding.errorGeneric')
  } finally {
    isSending.value = false
    scrollDown()
  }
}

const triggerDoc = () => docInput.value?.click()
const triggerReviewDoc = () => reviewDocInput.value?.click()

const handleDoc = async (file) => {
  if (!file) return
  errorMsg.value = ''
  const fd = new FormData()
  fd.append('file', file)
  try {
    const res = await extractWizardDoc(fd)
    const data = res.data || {}
    documentText.value = data.text || ''
    docName.value = data.filename || file.name
    if (!files.value.some(f => f.name === file.name)) files.value.push(file)
  } catch (e) {
    errorMsg.value = (e && e.message) ? e.message : t('aiOnboarding.errorGeneric')
  }
}

const onDocSelect = (e) => { handleDoc(e.target.files[0]); e.target.value = '' }
const onReviewDocSelect = (e) => {
  const f = e.target.files[0]
  if (f && !files.value.some(x => x.name === f.name)) files.value.push(f)
  e.target.value = ''
}
const removeDoc = () => { documentText.value = ''; docName.value = '' }
const removeFile = (i) => files.value.splice(i, 1)

const start = () => {
  if (!editableRequirement.value.trim()) return
  emit('submit', {
    files: files.value,
    requirement: editableRequirement.value.trim(),
    seedText: editableSeedText.value.trim() || editableRequirement.value.trim(),
    includeGermanSources: includeGermanSources.value
  })
}

const close = () => emit('close')
</script>

<style scoped>
.wizard-overlay {
  position: fixed; inset: 0; z-index: 9000; background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center; padding: 20px;
}
.wizard-modal {
  width: 100%; max-width: 660px; height: 86vh; max-height: 720px; background: #fff;
  border-radius: 14px; display: flex; flex-direction: column; overflow: hidden;
  font-family: 'JetBrains Mono', 'Space Grotesk', -apple-system, sans-serif;
  box-shadow: 0 20px 60px rgba(0,0,0,0.3);
}
.wizard-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 20px; background: #000; color: #fff; flex-shrink: 0;
}
.wizard-title { display: flex; align-items: center; gap: 10px; font-weight: 700; letter-spacing: 0.5px; }
.wizard-logo { height: 22px; width: auto; filter: brightness(0) invert(1); }
.wizard-close { background: none; border: none; color: #fff; font-size: 24px; line-height: 1; cursor: pointer; opacity: 0.7; }
.wizard-close:hover { opacity: 1; }

/* Chat */
.chat-area { flex: 1; overflow-y: auto; padding: 18px 20px; display: flex; flex-direction: column; gap: 14px; background: #fafafa; }
.chat-msg { display: flex; gap: 10px; max-width: 88%; }
.chat-msg.user { align-self: flex-end; flex-direction: row-reverse; }
.chat-avatar {
  width: 30px; height: 30px; border-radius: 50%; flex-shrink: 0; display: flex; align-items: center; justify-content: center;
  font-size: 0.66rem; font-weight: 700; color: #fff; background: #000;
}
.chat-msg.assistant .chat-avatar { background: #ff6b2c; }
.chat-bubble { padding: 10px 14px; border-radius: 12px; font-size: 0.88rem; line-height: 1.5; background: #fff; border: 1px solid #ececec; color: #1a1a1a; }
.chat-msg.user .chat-bubble { background: #000; color: #fff; border-color: #000; }
.chat-bubble.typing { color: #999; font-style: italic; }

.doc-chip { margin: 0 20px; padding: 6px 10px; background: #fff4ee; border: 1px solid #ffd9c2; border-radius: 6px; font-size: 0.78rem; color: #b3540f; display: flex; align-items: center; gap: 6px; }
.doc-chip button { margin-left: auto; background: none; border: none; color: #b3540f; cursor: pointer; font-size: 14px; }
.werror { color: #d9480f; font-size: 0.8rem; margin: 6px 20px 0; }

.chat-footer { display: flex; align-items: flex-end; gap: 8px; padding: 12px 16px; border-top: 1px solid #eee; background: #fff; flex-shrink: 0; }
.attach-btn { background: #f3f3f3; border: 1px solid #e0e0e0; border-radius: 8px; width: 40px; height: 40px; cursor: pointer; font-size: 16px; flex-shrink: 0; }
.attach-btn:hover:not(:disabled) { border-color: #ff6b2c; }
.chat-input { flex: 1; resize: none; padding: 10px 12px; border: 1.5px solid #e0e0e0; border-radius: 8px; font-family: inherit; font-size: 0.9rem; outline: none; max-height: 120px; }
.chat-input:focus { border-color: #ff6b2c; }
.send-btn { background: #ff6b2c; color: #fff; border: none; border-radius: 8px; padding: 0 18px; height: 40px; font-family: inherit; font-weight: 700; font-size: 0.85rem; cursor: pointer; flex-shrink: 0; }
.send-btn:disabled { opacity: 0.45; cursor: not-allowed; }

/* Review */
.review-area { flex: 1; overflow-y: auto; padding: 18px 20px; }
.review-title { font-size: 1.1rem; font-weight: 700; margin-bottom: 14px; }
.rfield { display: flex; flex-direction: column; gap: 5px; margin-bottom: 16px; }
.rlabel { font-weight: 600; font-size: 0.85rem; }
.rfield textarea { width: 100%; padding: 10px 12px; border: 1.5px solid #e0e0e0; border-radius: 8px; font-family: inherit; font-size: 0.85rem; line-height: 1.5; resize: vertical; outline: none; }
.rfield textarea:focus { border-color: #ff6b2c; }
.rsource-optin { display: flex; align-items: flex-start; gap: 10px; margin-bottom: 16px; cursor: pointer; }
.rsource-optin input { margin-top: 3px; width: 16px; height: 16px; accent-color: #ff6b2c; }
.rsource-label { display: block; font-weight: 600; font-size: 0.84rem; }
.rsource-hint { display: block; font-size: 0.73rem; color: #999; line-height: 1.3; }
.rfiles { display: flex; flex-direction: column; gap: 5px; margin-bottom: 6px; }
.rfile { background: #fff; border: 1px solid #eee; border-radius: 6px; padding: 5px 10px; font-size: 0.8rem; display: flex; align-items: center; }
.rfile button { margin-left: auto; background: none; border: none; color: #999; cursor: pointer; }
.attach-line { background: none; border: none; color: #ff6b2c; font-weight: 600; font-size: 0.82rem; cursor: pointer; font-family: inherit; padding: 0; }

.review-footer { display: flex; align-items: center; gap: 10px; padding: 14px 20px; border-top: 1px solid #eee; background: #fafafa; flex-shrink: 0; }
.wizard-spacer { flex: 1; }
.wbtn-ghost { background: none; border: 1px solid #ddd; border-radius: 8px; padding: 9px 16px; font-family: inherit; font-size: 0.85rem; font-weight: 500; cursor: pointer; color: #555; }
.wbtn-ghost:hover { border-color: #999; }
.wbtn-primary { background: #ff6b2c; color: #fff; border: none; border-radius: 8px; padding: 10px 20px; font-family: inherit; font-size: 0.88rem; font-weight: 700; cursor: pointer; }
.wbtn-primary:hover:not(:disabled) { opacity: 0.92; }
.wbtn-primary:disabled { opacity: 0.45; cursor: not-allowed; }
</style>
