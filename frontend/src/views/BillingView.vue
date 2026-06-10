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
        <button class="billing-back" @click="goHome">← {{ $t('common.back') }}</button>
      </div>
    </header>

    <div class="billing-body">
      <p class="billing-sub">{{ $t('billing.subtitle') }}</p>

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
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.project_id">
            <td class="nowrap">{{ fmtDate(row.created_at) }}</td>
            <td>
              <input class="cell-input" v-model="row.project_name"
                     @change="save(row)" @blur="save(row)" :placeholder="$t('billing.project')" />
            </td>
            <td class="req">{{ truncate(row.requirement, 60) }}</td>
            <td><span class="bstatus" :class="row.status">{{ row.status }}</span></td>
            <td class="num">{{ row.cost_eur != null ? eur(row.cost_eur) : '—' }}</td>
            <td class="num">
              <input class="cell-price" type="number" min="0" step="1" v-model.number="row.billing_price_eur"
                     @change="save(row)" @blur="save(row)" /> €
            </td>
            <td class="num" :class="marginClass(row)">{{ row.margin_eur != null ? eur(row.margin_eur) : '—' }}</td>
          </tr>
        </tbody>
        <tfoot>
          <tr class="total-row">
            <td colspan="4">{{ $t('billing.total') }}</td>
            <td class="num">{{ eur(totalCost) }}</td>
            <td class="num">{{ eur(totalPrice) }}</td>
            <td class="num">{{ eur(totalMargin) }}</td>
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
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import werwolfLogo from '../assets/logo/werwolf-icon.svg'
import LanguageSwitcher from '../components/LanguageSwitcher.vue'
import { listBilling, updateBilling } from '../api/billing'

const router = useRouter()
const { t } = useI18n()

const rows = ref([])
const loading = ref(true)

const goHome = () => router.push('/')

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
  try {
    const res = await listBilling()
    rows.value = res.data || []
  } catch (e) { /* leer */ }
  loading.value = false
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

.billing-body { max-width: 1200px; margin: 0 auto; padding: 24px 22px; }
.billing-sub { color: #666; font-size: 0.88rem; margin-bottom: 18px; }
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

.per-project { margin-top: 26px; }
.per-project h3 { font-size: 0.95rem; margin-bottom: 10px; }
.billing-table.small { font-size: 0.8rem; }
.billing-hint { margin-top: 16px; font-size: 0.74rem; color: #999; }
</style>
