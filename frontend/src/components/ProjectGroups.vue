<template>
  <div class="project-groups">
    <!-- Titelzeile im Stil der History-Sektion -->
    <div class="pg-header">
      <div class="pg-line"></div>
      <span class="pg-title">{{ $t('groups.title') }}</span>
      <div class="pg-line"></div>
    </div>
    <p class="pg-sub">{{ $t('groups.subtitle') }}</p>

    <!-- Neues Projekt anlegen -->
    <div class="pg-create">
      <button v-if="!showCreate" class="pg-create-toggle" @click="showCreate = true">
        + {{ $t('groups.create') }}
      </button>

      <div v-else class="pg-create-form">
        <div class="pg-field">
          <label>{{ $t('groups.name') }}</label>
          <input v-model="newName" class="pg-input" :placeholder="$t('groups.namePlaceholder')" />
        </div>
        <div class="pg-field">
          <label>{{ $t('groups.seedFiles') }} <span class="pg-hint">(PDF, MD, TXT)</span></label>
          <input type="file" multiple accept=".pdf,.md,.txt,.markdown" @change="onFiles" class="pg-file" />
          <span v-if="newFiles.length" class="pg-hint">{{ newFiles.map(f => f.name).join(', ') }}</span>
        </div>
        <div class="pg-field">
          <label>{{ $t('groups.seedText') }} <span class="pg-hint">({{ $t('groups.optional') }})</span></label>
          <textarea v-model="newSeedText" class="pg-textarea" rows="3"
                    :placeholder="$t('groups.seedTextPlaceholder')"></textarea>
        </div>
        <div class="pg-create-actions">
          <button class="pg-btn pg-btn-primary" :disabled="creating || !newName.trim() || (newFiles.length === 0 && !newSeedText.trim())"
                  @click="submitCreate">
            {{ creating ? $t('groups.creating') : $t('groups.createBtn') }}
          </button>
          <button class="pg-btn" @click="resetCreate">{{ $t('common.cancel') }}</button>
        </div>
        <div v-if="createError" class="pg-error">{{ createError }}</div>
      </div>
    </div>

    <!-- Projektliste -->
    <div v-if="groups.length === 0 && !loading" class="pg-empty">{{ $t('groups.empty') }}</div>

    <div v-for="g in groups" :key="g.group_id" class="pg-card">
      <div class="pg-card-head" @click="toggle(g.group_id)">
        <span class="pg-card-name">{{ g.name }}</span>
        <span class="pg-card-meta mono">
          {{ g.files.length }} {{ $t('groups.files') }} · {{ g.runs.length }} {{ $t('groups.runs') }}
        </span>
        <span class="pg-card-arrow">{{ expanded === g.group_id ? '▾' : '▸' }}</span>
      </div>

      <div v-if="expanded === g.group_id" class="pg-card-body">
        <!-- Seed-Info -->
        <div class="pg-seed mono">
          <span v-for="f in g.files" :key="f.saved_filename" class="pg-seed-file">📄 {{ f.original_filename }}</span>
          <span v-if="g.seed_text" class="pg-seed-file">📝 {{ $t('groups.seedTextLabel') }}</span>
        </div>

        <!-- Neuer Run -->
        <div class="pg-newrun">
          <textarea v-model="runPrompts[g.group_id]" class="pg-textarea" rows="2"
                    :placeholder="$t('groups.newRunPlaceholder')"></textarea>
          <button class="pg-btn pg-btn-primary"
                  :disabled="!(runPrompts[g.group_id] || '').trim() || startingId === g.group_id"
                  @click="startRun(g)">
            {{ startingId === g.group_id ? $t('groups.starting') : $t('groups.startRun') }} →
          </button>
        </div>

        <!-- Bisherige Runs -->
        <div v-if="g.runs.length" class="pg-runs">
          <div v-for="(r, i) in [...g.runs].reverse()" :key="r.project_id" class="pg-run"
               @click="openRun(r)">
            <span class="pg-run-no mono">#{{ g.runs.length - i }}</span>
            <span class="pg-run-req">{{ truncate(r.requirement, 90) }}</span>
            <span class="pg-run-date mono">{{ fmtDate(r.created_at) }}</span>
          </div>
        </div>
        <div v-else class="pg-hint">{{ $t('groups.noRuns') }}</div>

        <button class="pg-delete" @click="removeGroup(g)">🗑 {{ $t('groups.delete') }}</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { listGroups, createGroup, deleteGroup } from '../api/groups'
import { setPendingGroupRun } from '../store/pendingUpload'

const router = useRouter()
const { t } = useI18n()

const groups = ref([])
const loading = ref(true)
const expanded = ref('')
const showCreate = ref(false)
const creating = ref(false)
const createError = ref('')
const newName = ref('')
const newSeedText = ref('')
const newFiles = ref([])
const runPrompts = reactive({})
const startingId = ref('')

const load = async () => {
  loading.value = true
  try {
    const res = await listGroups()
    if (res.success) groups.value = res.data || []
  } catch (e) { /* nicht eingeloggt o.ä. — Sektion bleibt leer */ }
  loading.value = false
}

const toggle = (id) => { expanded.value = expanded.value === id ? '' : id }

const onFiles = (e) => { newFiles.value = Array.from(e.target.files || []) }

const resetCreate = () => {
  showCreate.value = false
  createError.value = ''
  newName.value = ''
  newSeedText.value = ''
  newFiles.value = []
}

const submitCreate = async () => {
  creating.value = true
  createError.value = ''
  try {
    const fd = new FormData()
    fd.append('name', newName.value.trim())
    if (newSeedText.value.trim()) fd.append('seed_text', newSeedText.value.trim())
    newFiles.value.forEach(f => fd.append('files', f))
    const res = await createGroup(fd)
    if (res.success) {
      resetCreate()
      await load()
      expanded.value = res.data?.group_id || ''
    } else {
      createError.value = res.error || 'Error'
    }
  } catch (e) {
    createError.value = e.message || String(e)
  }
  creating.value = false
}

const startRun = (g) => {
  const prompt = (runPrompts[g.group_id] || '').trim()
  if (!prompt) return
  startingId.value = g.group_id
  // Seed liegt serverseitig — Process.vue startet den Run über die Group-API
  setPendingGroupRun(g.group_id, prompt)
  router.push({ name: 'Process', params: { projectId: 'new' } })
}

const openRun = (r) => {
  if (r.project_id) router.push({ name: 'Process', params: { projectId: r.project_id } })
}

const removeGroup = async (g) => {
  if (!window.confirm(t('groups.confirmDelete', { name: g.name }))) return
  try {
    await deleteGroup(g.group_id)
    await load()
  } catch (e) { /* ignore */ }
}

const truncate = (s, n) => (s && s.length > n ? s.slice(0, n) + '…' : (s || ''))
const fmtDate = (iso) => {
  if (!iso) return ''
  try { return new Date(iso).toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: '2-digit' }) }
  catch { return '' }
}

onMounted(load)
</script>

<style scoped>
.project-groups { max-width: 860px; margin: 48px auto 0; padding: 0 20px; font-family: 'IBM Plex Mono', 'Courier New', monospace; }
.mono { font-family: inherit; }

.pg-header { display: flex; align-items: center; gap: 14px; margin-bottom: 6px; }
.pg-line { flex: 1; height: 1px; background: #e0e0e0; }
.pg-title { font-size: 0.78rem; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; color: #666; }
.pg-sub { text-align: center; color: #999; font-size: 0.74rem; margin: 0 0 18px; }

.pg-create { text-align: center; margin-bottom: 20px; }
.pg-create-toggle { background: #000; color: #fff; border: none; padding: 10px 20px; font-family: inherit; font-size: 0.8rem; font-weight: 700; cursor: pointer; letter-spacing: 0.5px; }
.pg-create-toggle:hover { background: #ff6b2c; }

.pg-create-form { text-align: left; background: #fff; border: 1px solid #e0e0e0; padding: 18px; }
.pg-field { margin-bottom: 12px; }
.pg-field label { display: block; font-size: 0.74rem; font-weight: 700; margin-bottom: 5px; color: #333; }
.pg-hint { color: #999; font-weight: 400; font-size: 0.7rem; }
.pg-input, .pg-textarea { width: 100%; box-sizing: border-box; padding: 8px 10px; border: 1.5px solid #e0e0e0; font-family: inherit; font-size: 0.8rem; background: #fafafa; }
.pg-input:focus, .pg-textarea:focus { border-color: #ff6b2c; outline: none; background: #fff; }
.pg-file { font-size: 0.74rem; }
.pg-create-actions { display: flex; gap: 8px; margin-top: 4px; }
.pg-btn { padding: 8px 16px; border: 1px solid #ccc; background: #fff; font-family: inherit; font-size: 0.76rem; font-weight: 700; cursor: pointer; }
.pg-btn-primary { background: #ff6b2c; border-color: #ff6b2c; color: #fff; }
.pg-btn-primary:disabled { opacity: 0.5; cursor: default; }
.pg-error { color: #c0392b; font-size: 0.74rem; margin-top: 8px; }
.pg-empty { text-align: center; color: #aaa; font-size: 0.76rem; padding: 12px 0 4px; }

.pg-card { background: #fff; border: 1px solid #e0e0e0; margin-bottom: 10px; }
.pg-card-head { display: flex; align-items: center; gap: 12px; padding: 12px 16px; cursor: pointer; }
.pg-card-head:hover { background: #fafafa; }
.pg-card-name { font-weight: 700; font-size: 0.86rem; }
.pg-card-meta { margin-left: auto; color: #999; font-size: 0.72rem; }
.pg-card-arrow { color: #ff6b2c; }

.pg-card-body { border-top: 1px solid #f0f0f0; padding: 14px 16px; }
.pg-seed { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 12px; }
.pg-seed-file { font-size: 0.72rem; color: #666; background: #f5f5f5; padding: 3px 8px; }

.pg-newrun { display: flex; gap: 8px; align-items: flex-start; margin-bottom: 14px; }
.pg-newrun .pg-textarea { flex: 1; }
.pg-newrun .pg-btn { white-space: nowrap; margin-top: 2px; }

.pg-runs { border-top: 1px dashed #e8e8e8; padding-top: 8px; }
.pg-run { display: flex; align-items: center; gap: 10px; padding: 7px 6px; cursor: pointer; font-size: 0.76rem; }
.pg-run:hover { background: #fff7f2; }
.pg-run-no { color: #ff6b2c; font-weight: 700; }
.pg-run-req { flex: 1; color: #444; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.pg-run-date { color: #aaa; font-size: 0.7rem; }

.pg-delete { margin-top: 10px; background: none; border: none; color: #bbb; font-family: inherit; font-size: 0.72rem; cursor: pointer; padding: 0; }
.pg-delete:hover { color: #c0392b; }
</style>
