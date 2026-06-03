<template>
  <div class="shared-page">
    <header class="shared-header">
      <div class="shared-brand">
        <img :src="werwolfLogo" alt="Werwolf Media" class="shared-logo" />
        <span class="shared-brand-title">MIROFISH</span>
        <span class="shared-brand-by">by Werwolf Media</span>
      </div>
      <LanguageSwitcher />
    </header>

    <!-- Fehlerzustände -->
    <div v-if="fatalError" class="shared-error">
      <div class="shared-error-box">
        <div class="shared-error-icon">⚠</div>
        <p>{{ fatalErrorText }}</p>
      </div>
    </div>

    <div v-else class="shared-body">
      <!-- Bericht -->
      <section class="shared-report">
        <div v-if="loadingReport" class="shared-loading">{{ $t('common.loading') }}</div>
        <template v-else>
          <span class="shared-tag">{{ $t('step4.predictionReport') }}</span>
          <h1 class="shared-report-title">{{ report.title }}</h1>
          <p v-if="report.summary" class="shared-report-summary">{{ report.summary }}</p>
          <div class="shared-markdown" v-html="renderMarkdown(report.markdown)"></div>
        </template>
      </section>

      <!-- Chat -->
      <aside class="shared-chat">
        <div class="shared-chat-head">
          <div class="shared-tabs">
            <button :class="{ active: mode === 'report' }" @click="setMode('report')">{{ $t('shared.reportAgent') }}</button>
            <button :class="{ active: mode === 'agent' }" @click="setMode('agent')">{{ $t('shared.individualAgent') }}</button>
          </div>
          <select v-if="mode === 'agent'" v-model="selectedAgent" class="shared-agent-select">
            <option :value="null" disabled>{{ $t('shared.selectAgent') }}</option>
            <option v-for="a in profiles" :key="a.agent_id" :value="a.agent_id">
              {{ a.username }}<template v-if="a.profession"> · {{ a.profession }}</template>
            </option>
          </select>
        </div>

        <div class="shared-msgs" ref="msgArea">
          <div v-for="(m, i) in messages" :key="i" class="smsg" :class="m.role">
            <div class="smsg-avatar">{{ m.role === 'user' ? '·' : 'KI' }}</div>
            <div class="smsg-bubble" v-html="renderMarkdown(m.content)"></div>
          </div>
          <div v-if="isSending" class="smsg assistant">
            <div class="smsg-avatar">KI</div>
            <div class="smsg-bubble typing">{{ $t('shared.thinking') }}</div>
          </div>
        </div>

        <p v-if="chatError" class="shared-cherr">{{ chatError }}</p>

        <div class="shared-input-row">
          <textarea
            v-model="input"
            rows="1"
            class="shared-input"
            :placeholder="$t('shared.inputPlaceholder')"
            :disabled="isSending || (mode === 'agent' && selectedAgent === null)"
            @keydown.enter.exact.prevent="send"
          ></textarea>
          <button class="shared-send" :disabled="!canSend" @click="send">{{ $t('shared.send') }}</button>
        </div>
      </aside>
    </div>

    <footer class="shared-foot">{{ $t('shared.poweredBy') }}</footer>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import werwolfLogo from '../assets/logo/werwolf-icon.svg'
import LanguageSwitcher from './LanguageSwitcher.vue'
import { getSharedReport, getSharedProfiles, sharedChat, sharedInterview } from '../api/shared'

const props = defineProps({ token: String })
const { t } = useI18n()

const report = ref({ title: '', summary: '', markdown: '', agentsAvailable: 0 })
const loadingReport = ref(true)
const fatalError = ref('')
const profiles = ref([])
const mode = ref('report')
const selectedAgent = ref(null)
const messages = ref([])
const input = ref('')
const isSending = ref(false)
const chatError = ref('')
const msgArea = ref(null)

const fatalErrorText = computed(() => {
  if (fatalError.value === 'share_revoked') return t('shared.revoked')
  return t('shared.invalid')
})

const canSend = computed(() =>
  !isSending.value && input.value.trim() && !(mode.value === 'agent' && selectedAgent.value === null)
)

const renderMarkdown = (md) => {
  let html = String(md || '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  html = html.replace(/```([\s\S]*?)```/g, '<pre>$1</pre>')
  html = html.replace(/^######\s+(.+)$/gm, '<h6>$1</h6>')
    .replace(/^#####\s+(.+)$/gm, '<h5>$1</h5>')
    .replace(/^####\s+(.+)$/gm, '<h4>$1</h4>')
    .replace(/^###\s+(.+)$/gm, '<h3>$1</h3>')
    .replace(/^##\s+(.+)$/gm, '<h2>$1</h2>')
    .replace(/^#\s+(.+)$/gm, '<h1>$1</h1>')
  html = html.replace(/^>\s+(.+)$/gm, '<blockquote>$1</blockquote>')
  html = html.replace(/^[-*]\s+(.+)$/gm, '<li>$1</li>')
  html = html.replace(/(<li>[\s\S]*?<\/li>)/g, '<ul>$1</ul>')
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>')
  html = html.replace(/\n{2,}/g, '</p><p>').replace(/\n/g, '<br>')
  return '<p>' + html + '</p>'
}

const scrollDown = () => nextTick(() => { if (msgArea.value) msgArea.value.scrollTop = msgArea.value.scrollHeight })

const setMode = (m) => { mode.value = m; chatError.value = '' }

const send = async () => {
  if (!canSend.value) return
  const text = input.value.trim()
  chatError.value = ''
  messages.value.push({ role: 'user', content: text })
  input.value = ''
  isSending.value = true
  scrollDown()
  try {
    let reply = ''
    if (mode.value === 'report') {
      const history = messages.value.slice(0, -1).filter(m => m.role === 'user' || m.role === 'assistant')
      const res = await sharedChat(props.token, text, history)
      reply = (res.data && res.data.response) || ''
    } else {
      const res = await sharedInterview(props.token, selectedAgent.value, text)
      const rd = (res.data && res.data.result) || res.data || {}
      const dict = rd.results || rd
      const id = selectedAgent.value
      const r = dict[`reddit_${id}`] || dict[`twitter_${id}`] || Object.values(dict)[0]
      reply = (r && (r.response || r.answer)) || ''
    }
    messages.value.push({ role: 'assistant', content: reply || t('shared.thinking') })
  } catch (e) {
    if (e && e.message === 'share_limit') chatError.value = t('shared.limitReached')
    else if (e && e.message === 'share_revoked') { fatalError.value = 'share_revoked' }
    else chatError.value = t('aiOnboarding.errorGeneric')
  } finally {
    isSending.value = false
    scrollDown()
  }
}

onMounted(async () => {
  try {
    const res = await getSharedReport(props.token)
    report.value = res.data || report.value
    loadingReport.value = false
  } catch (e) {
    loadingReport.value = false
    fatalError.value = (e && e.message) || 'share_invalid'
    return
  }
  try {
    const res = await getSharedProfiles(props.token)
    profiles.value = (res.data && res.data.profiles) || []
  } catch (e) { /* Chat mit Agenten optional */ }
})
</script>

<style scoped>
.shared-page { min-height: 100vh; display: flex; flex-direction: column; background: #f4f4f5; font-family: 'JetBrains Mono', 'Space Grotesk', -apple-system, sans-serif; color: #1a1a1a; }
.shared-header { display: flex; align-items: center; justify-content: space-between; padding: 12px 22px; background: #000; color: #fff; }
.shared-brand { display: flex; align-items: baseline; gap: 8px; }
.shared-logo { height: 22px; filter: brightness(0) invert(1); align-self: center; }
.shared-brand-title { font-weight: 800; letter-spacing: 1px; }
.shared-brand-by { font-size: 0.7rem; opacity: 0.6; }

.shared-error { flex: 1; display: flex; align-items: center; justify-content: center; padding: 40px; }
.shared-error-box { text-align: center; max-width: 420px; }
.shared-error-icon { font-size: 40px; margin-bottom: 12px; }

.shared-body { flex: 1; display: flex; gap: 18px; padding: 22px; max-width: 1400px; margin: 0 auto; width: 100%; box-sizing: border-box; align-items: flex-start; }
.shared-report { flex: 1; min-width: 0; background: #fff; border: 1px solid #e6e6e6; border-radius: 12px; padding: 26px 30px; }
.shared-loading { color: #999; }
.shared-tag { display: inline-block; font-size: 0.7rem; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; color: #ff6b2c; border: 1px solid #ff6b2c; border-radius: 4px; padding: 2px 8px; }
.shared-report-title { font-size: 1.6rem; font-weight: 800; margin: 10px 0 6px; line-height: 1.25; }
.shared-report-summary { font-style: italic; color: #555; margin-bottom: 18px; }
.shared-markdown { font-size: 0.92rem; line-height: 1.65; }
.shared-markdown :deep(h1), .shared-markdown :deep(h2), .shared-markdown :deep(h3) { font-weight: 700; margin: 18px 0 8px; line-height: 1.3; }
.shared-markdown :deep(h2) { font-size: 1.2rem; border-left: 3px solid #ff6b2c; padding-left: 10px; }
.shared-markdown :deep(p) { margin: 8px 0; }
.shared-markdown :deep(ul) { margin: 8px 0 8px 18px; }
.shared-markdown :deep(blockquote) { border-left: 3px solid #ccc; padding: 4px 12px; color: #555; font-style: italic; margin: 10px 0; }
.shared-markdown :deep(code) { background: #f3f3f3; padding: 1px 4px; border-radius: 3px; }
.shared-markdown :deep(pre) { background: #f3f3f3; padding: 10px; border-radius: 6px; overflow: auto; }

.shared-chat { width: 380px; flex-shrink: 0; background: #fff; border: 1px solid #e6e6e6; border-radius: 12px; display: flex; flex-direction: column; position: sticky; top: 22px; height: calc(100vh - 130px); }
.shared-chat-head { padding: 12px; border-bottom: 1px solid #eee; }
.shared-tabs { display: flex; gap: 6px; }
.shared-tabs button { flex: 1; padding: 8px; border: 1px solid #e0e0e0; background: #fafafa; border-radius: 7px; font-family: inherit; font-size: 0.78rem; cursor: pointer; }
.shared-tabs button.active { background: #000; color: #fff; border-color: #000; }
.shared-agent-select { margin-top: 8px; width: 100%; padding: 8px; border: 1px solid #e0e0e0; border-radius: 7px; font-family: inherit; font-size: 0.8rem; }

.shared-msgs { flex: 1; overflow-y: auto; padding: 14px; display: flex; flex-direction: column; gap: 12px; }
.smsg { display: flex; gap: 8px; max-width: 90%; }
.smsg.user { align-self: flex-end; flex-direction: row-reverse; }
.smsg-avatar { width: 26px; height: 26px; border-radius: 50%; flex-shrink: 0; display: flex; align-items: center; justify-content: center; font-size: 0.6rem; font-weight: 700; color: #fff; background: #ff6b2c; }
.smsg.user .smsg-avatar { background: #000; }
.smsg-bubble { padding: 9px 12px; border-radius: 11px; font-size: 0.85rem; line-height: 1.5; background: #f6f6f6; }
.smsg.user .smsg-bubble { background: #000; color: #fff; }
.smsg-bubble.typing { color: #999; font-style: italic; }

.shared-cherr { color: #d9480f; font-size: 0.78rem; padding: 0 14px; }
.shared-input-row { display: flex; gap: 8px; padding: 12px; border-top: 1px solid #eee; }
.shared-input { flex: 1; resize: none; padding: 9px 11px; border: 1.5px solid #e0e0e0; border-radius: 8px; font-family: inherit; font-size: 0.85rem; outline: none; max-height: 100px; }
.shared-input:focus { border-color: #ff6b2c; }
.shared-send { background: #ff6b2c; color: #fff; border: none; border-radius: 8px; padding: 0 16px; font-family: inherit; font-weight: 700; font-size: 0.82rem; cursor: pointer; }
.shared-send:disabled { opacity: 0.45; cursor: not-allowed; }

.shared-foot { text-align: center; padding: 14px; font-size: 0.72rem; color: #999; }

@media (max-width: 900px) {
  .shared-body { flex-direction: column; }
  .shared-chat { width: 100%; position: static; height: 70vh; }
}
</style>
