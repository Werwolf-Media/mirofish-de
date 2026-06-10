<template>
  <div class="billing-page">
    <header class="billing-header">
      <div class="billing-brand" @click="goHome">
        <img :src="werwolfLogo" alt="Werwolf Media" class="billing-logo" />
        <span class="billing-brand-title">MIROFISH</span>
        <span class="billing-brand-by">{{ $t('billing.title') }}</span>
      </div>
      <div class="billing-head-right">
        <LanguageSwitcher />
        <button v-if="authed" class="billing-back" @click="adminLogout">{{ $t('billing.adminLogout') }}</button>
        <button class="billing-back" @click="goHome">← {{ $t('common.back') }}</button>
      </div>
    </header>

    <!-- Admin-Login (nur Inhaber) -->
    <div v-if="!authed" class="admin-login">
      <div class="admin-card">
        <h2>{{ $t('billing.adminTitle') }}</h2>
        <p class="admin-hint">{{ $t('billing.adminHint') }}</p>
        <input ref="pwInput" v-model="pw" type="password" class="admin-input"
               :placeholder="$t('login.passwordPlaceholder')" :disabled="loggingIn"
               @keydown.enter.prevent="doAdminLogin" autocomplete="current-password" />
        <p v-if="loginError" class="admin-err">{{ $t('billing.adminWrong') }}</p>
        <button class="admin-btn" :disabled="loggingIn || !pw" @click="doAdminLogin">
          {{ loggingIn ? $t('login.submitting') : $t('billing.adminSubmit') }}
        </button>
      </div>
    </div>

    <div v-else class="billing-body">
      <p class="billing-sub">{{ $t('billing.subtitle') }}</p>

      <div class="default-price-bar">
        <label>{{ $t('billing.defaultPrice') }}</label>
        <input type="number" min="0" step="1" v-model.number="defaultPrice"
               @keydown.enter.prevent="saveDefault" class="default-price-input" /> €
        <button class="default-price-btn" @click="saveDefault">{{ defaultSaved ? $t('share.copied') : $t('billing.savePrice') }}</button>
        <span class="default-price-hint">{{ $t('billing.defaultPriceHint') }}</span>
      </div>

      <div v-if="loading" class="billing-loading">{{ $t('common.loading') }}</div>
      <div v-else-if="rows.length === 0" class="billing-empty">{{ $t('billing.empty') }}</div>

      <table v-else class="billing-table">
        <thead>
          <tr>
            <th>{{ $t('billing.date') }}</th>
            <th>{{ $t('billing.project') }}</th>
            <th>{{ $t('billing.requirement') }}</th>
            <th>{{ $t('billing.status') }}</th>
            <th class="num">{{ $t('billing.cost') }}</th>
            <th class="num">{{ $t('billing.price') }}</th>
            <th class="num">{{ $t('billing.margin') }}</th>
            <th class="actions-col">{{ $t('billing.actions') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.project_id" :class="{ invoiced: row.invoiced }">
            <td class="nowrap">{{ fmtDate(row.created_at) }}</td>
            <td>
              <input class="cell-input" v-model="row.project_name"
                     @change="save(row)" @blur="save(row)" :placeholder="$t('billing.project')" />
            </td>
            <td class="req">{{ truncate(row.requirement, 60) }}</td>
            <td>
              <span class="bstatus" :class="row.status">{{ row.status }}</span>
              <span v-if="row.invoiced" class="bstatus invoiced-badge">{{ $t('billing.invoiced') }}</span>
            </td>
            <td class="num">{{ row.cost_eur != null ? eur(row.cost_eur) : '—' }}</td>
            <td class="num">
              <input class="cell-price" type="number" min="0" step="1" v-model.number="row.billing_price_eur"
                     @change="save(row)" @blur="save(row)" /> €
            </td>
            <td class="num" :class="marginClass(row)">{{ row.margin_eur != null ? eur(row.margin_eur) : '—' }}</td>
            <td class="actions-col">
              <button class="act-btn" @click="markInvoiced(row)" :title="row.invoiced ? $t('billing.markOpen') : $t('billing.markInvoiced')">
                {{ row.invoiced ? $t('billing.markOpen') : $t('billing.markInvoiced') }}
              </button>
              <button class="act-del" @click="removeRow(row)" :title="$t('billing.delete')">🗑</button>
            </td>
          </tr>
        </tbody>
        <tfoot>
          <tr class="total-row">
            <td colspan="4">{{ $t('billing.total') }}</td>
            <td class="num">{{ eur(totalCost) }}</td>
            <td class="num">{{ eur(totalPrice) }}</td>
            <td class="num">{{ eur(totalMargin) }}</td>
            <td></td>
          </tr>
          <tr class="open-row">
            <td colspan="4">{{ $t('billing.openTotal') }}</td>
            <td></td>
            <td class="num">{{ eur(openTotal) }}</td>
            <td colspan="2"></td>
          </tr>
        </tfoot>
      </table>

      <!-- Summe je Projekt -->
      <div v-if="rows.length" class="per-project">
        <h3>{{ $t('billing.perProject') }}</h3>
        <table class="billing-table small">
          <thead>
            <tr><th>{{ $t('billing.project') }}</th><th class="num">{{ $t('billing.cost') }}</th><th class="num">{{ $t('billing.price') }}</th><th class="num">{{ $t('billing.margin') }}</th></tr>
          </thead>
          <tbody>
            <tr v-for="g in perProject" :key="g.name">
              <td>{{ g.name || '—' }}</td>
              <td class="num">{{ eur(g.cost) }}</td>
              <td class="num">{{ eur(g.price) }}</td>
              <td class="num">{{ eur(g.margin) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <p class="billing-hint">{{ $t('billing.priceHint') }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import werwolfLogo from '../assets/logo/werwolf-icon.svg'
import LanguageSwitcher from '../components/LanguageSwitcher.vue'
import { listBilling, updateBilling, adminLogin, setDefaultPrice, setInvoiced, deleteBilling } from '../api/billing'

const router = useRouter()
const { t } = useI18n()

const rows = ref([])
const loading = ref(true)
const defaultPrice = ref(50)
const defaultSaved = ref(false)

// Admin-Zugang (nur Inhaber)
const adminToken = ref(localStorage.getItem('adminToken') || '')
const authed = ref(!!adminToken.value)
const pw = ref('')
const loggingIn = ref(false)
const loginError = ref(false)
const pwInput = ref(null)

const goHome = () => router.push('/')

const doAdminLogin = async () => {
  if (!pw.value || loggingIn.value) return
  loginError.value = false
  loggingIn.value = true
  try {
    const res = await adminLogin(pw.value)
    if (res && res.success && res.token) {
      localStorage.setItem('adminToken', res.token)
      adminToken.value = res.token
      authed.value = true
      pw.value = ''
      await load()
    } else {
      loginError.value = true
    }
  } catch (e) {
    loginError.value = true
  } finally {
    loggingIn.value = false
  }
}

const adminLogout = () => {
  localStorage.removeItem('adminToken')
  adminToken.value = ''
  authed.value = false
  rows.value = []
}

const load = async () => {
  loading.value = true
  try {
    const res = await listBilling()
    rows.value = res.data || []
    if (typeof res.default_billing_price_eur === 'number') defaultPrice.value = res.default_billing_price_eur
  } catch (e) {
    if (e && e.message === 'admin_required') adminLogout()
  } finally {
    loading.value = false
  }
}

const saveDefault = async () => {
  try {
    const res = await setDefaultPrice(Number(defaultPrice.value) || 0)
    if (res.data && typeof res.data.default_billing_price_eur === 'number') {
      defaultPrice.value = res.data.default_billing_price_eur
    }
    defaultSaved.value = true
    setTimeout(() => { defaultSaved.value = false }, 1500)
  } catch (e) { /* ignore */ }
}

const fmtDate = (iso) => {
  if (!iso) return '—'
  try { return new Date(iso).toLocaleDateString() } catch { return iso }
}
const truncate = (s, n) => { s = s || ''; return s.length > n ? s.slice(0, n) + '…' : s }
const eur = (v) => `${(Number(v) || 0).toFixed(2)} €`
const marginClass = (row) => row.margin_eur == null ? '' : (row.margin_eur >= 0 ? 'pos' : 'neg')

const totalCost = computed(() => rows.value.reduce((s, r) => s + (r.cost_eur || 0), 0))
const totalPrice = computed(() => rows.value.reduce((s, r) => s + (Number(r.billing_price_eur) || 0), 0))
const totalMargin = computed(() => rows.value.reduce((s, r) => s + (r.margin_eur != null ? r.margin_eur : (Number(r.billing_price_eur) || 0)), 0))
const openTotal = computed(() => rows.value.filter(r => !r.invoiced).reduce((s, r) => s + (Number(r.billing_price_eur) || 0), 0))

const perProject = computed(() => {
  const map = {}
  for (const r of rows.value) {
    const name = (r.project_name || '').trim()
    if (!map[name]) map[name] = { name, cost: 0, price: 0, margin: 0 }
    map[name].cost += r.cost_eur || 0
    map[name].price += Number(r.billing_price_eur) || 0
    map[name].margin += r.margin_eur != null ? r.margin_eur : (Number(r.billing_price_eur) || 0)
  }
  return Object.values(map)
})

const markInvoiced = async (row) => {
  const target = !row.invoiced
  try {
    const res = await setInvoiced(row.project_id, target)
    if (res.data) row.invoiced = res.data.invoiced
    else row.invoiced = target
  } catch (e) { /* ignore */ }
}

const removeRow = async (row) => {
  if (!window.confirm(t('billing.confirmDelete'))) return
  try {
    await deleteBilling(row.project_id)
    rows.value = rows.value.filter(r => r.project_id !== row.project_id)
  } catch (e) { /* ignore */ }
}

const save = async (row) => {
  try {
    const res = await updateBilling(row.project_id, {
      project_name: row.project_name,
      billing_price_eur: Number(row.billing_price_eur) || 0
    })
    if (res.data) {
      row.cost_eur = res.data.cost_eur
      row.margin_eur = res.data.margin_eur
      row.billing_price_eur = res.data.billing_price_eur
    }
  } catch (e) { /* still local */ }
}

onMounted(async () => {
  if (authed.value) {
    await load()
  } else {
    loading.value = false
    nextTick(() => pwInput.value?.focus())
  }
})
</script>

<style scoped>
.billing-page { min-height: 100vh; background: #f4f4f5; font-family: 'JetBrains Mono', 'Space Grotesk', -apple-system, sans-serif; color: #1a1a1a; }
.billing-header { display: flex; align-items: center; justify-content: space-between; padding: 12px 22px; background: #000; color: #fff; }
.billing-brand { display: flex; align-items: baseline; gap: 8px; cursor: pointer; }
.billing-logo { height: 22px; filter: brightness(0) invert(1); align-self: center; }
.billing-brand-title { font-weight: 800; letter-spacing: 1px; }
.billing-brand-by { font-size: 0.72rem; opacity: 0.6; }
.billing-head-right { display: flex; align-items: center; gap: 14px; }
.billing-back { background: none; border: 1px solid rgba(255,255,255,0.3); color: #fff; border-radius: 6px; padding: 5px 12px; font-family: inherit; font-size: 0.8rem; cursor: pointer; }
.billing-back:hover { border-color: rgba(255,255,255,0.6); }

.admin-login { display: flex; justify-content: center; padding: 60px 22px; }
.admin-card { width: 100%; max-width: 360px; background: #fff; border: 1px solid #e6e6e6; border-radius: 12px; padding: 28px; text-align: center; }
.admin-card h2 { font-size: 1.15rem; font-weight: 800; margin-bottom: 4px; }
.admin-hint { font-size: 0.82rem; color: #888; margin-bottom: 18px; }
.admin-input { width: 100%; padding: 11px 13px; border: 1.5px solid #e0e0e0; border-radius: 8px; font-family: inherit; font-size: 0.95rem; outline: none; }
.admin-input:focus { border-color: #ff6b2c; }
.admin-err { color: #d9480f; font-size: 0.8rem; margin-top: 8px; }
.admin-btn { width: 100%; margin-top: 16px; padding: 12px; background: #ff6b2c; color: #fff; border: none; border-radius: 8px; font-family: inherit; font-weight: 700; cursor: pointer; }
.admin-btn:disabled { opacity: 0.45; cursor: not-allowed; }

.billing-body { max-width: 1200px; margin: 0 auto; padding: 24px 22px; }
.billing-sub { color: #666; font-size: 0.88rem; margin-bottom: 14px; }
.default-price-bar { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; background: #fff; border: 1px solid #e6e6e6; border-radius: 10px; padding: 12px 16px; margin-bottom: 20px; font-size: 0.86rem; }
.default-price-bar label { font-weight: 600; }
.default-price-input { width: 70px; padding: 6px 8px; border: 1.5px solid #e0e0e0; border-radius: 6px; font-family: inherit; font-size: 0.86rem; text-align: right; }
.default-price-input:focus { border-color: #ff6b2c; outline: none; }
.default-price-btn { background: #ff6b2c; color: #fff; border: none; border-radius: 7px; padding: 7px 14px; font-family: inherit; font-weight: 700; font-size: 0.8rem; cursor: pointer; }
.default-price-hint { color: #999; font-size: 0.74rem; margin-left: 6px; }
.billing-loading, .billing-empty { color: #999; padding: 30px 0; }

.billing-table { width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #e6e6e6; border-radius: 10px; overflow: hidden; font-size: 0.84rem; }
.billing-table th, .billing-table td { padding: 9px 12px; text-align: left; border-bottom: 1px solid #f0f0f0; }
.billing-table th { background: #fafafa; font-weight: 700; font-size: 0.74rem; text-transform: uppercase; letter-spacing: 0.4px; color: #666; }
.billing-table th.num, .billing-table td.num { text-align: right; white-space: nowrap; }
.nowrap { white-space: nowrap; }
.req { color: #777; }
.cell-input { width: 100%; min-width: 120px; padding: 5px 8px; border: 1px solid transparent; border-radius: 6px; font-family: inherit; font-size: 0.84rem; background: #fafafa; }
.cell-input:focus { border-color: #ff6b2c; outline: none; background: #fff; }
.cell-price { width: 64px; padding: 5px 6px; border: 1px solid #e0e0e0; border-radius: 6px; font-family: inherit; font-size: 0.84rem; text-align: right; }
.cell-price:focus { border-color: #ff6b2c; outline: none; }
.bstatus { font-size: 0.72rem; padding: 2px 7px; border-radius: 4px; background: #eee; color: #666; }
.bstatus.completed { background: #e6f4ea; color: #2f9e44; }
.bstatus.running { background: #fff4e6; color: #e8590c; }
.num.pos { color: #2f9e44; }
.num.neg { color: #e03131; }
.total-row td { font-weight: 700; background: #fafafa; border-top: 2px solid #e6e6e6; }
.open-row td { background: #fafafa; color: #555; font-size: 0.8rem; }
.actions-col { text-align: right; white-space: nowrap; }
.act-btn { background: none; border: 1px solid #ddd; border-radius: 6px; padding: 4px 9px; font-family: inherit; font-size: 0.72rem; cursor: pointer; color: #444; }
.act-btn:hover { border-color: #2f9e44; color: #2f9e44; }
.act-del { background: none; border: 1px solid #eee; border-radius: 6px; padding: 4px 8px; margin-left: 6px; cursor: pointer; font-size: 0.8rem; }
.act-del:hover { border-color: #e03131; }
tr.invoiced { opacity: 0.6; }
tr.invoiced .cell-input, tr.invoiced .cell-price { background: transparent; }
.invoiced-badge { background: #e6f4ea !important; color: #2f9e44 !important; margin-left: 6px; }

.per-project { margin-top: 26px; }
.per-project h3 { font-size: 0.95rem; margin-bottom: 10px; }
.billing-table.small { font-size: 0.8rem; }
.billing-hint { margin-top: 16px; font-size: 0.74rem; color: #999; }
</style>
