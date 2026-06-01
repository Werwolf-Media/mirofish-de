<template>
  <div class="login-overlay">
    <div class="login-topbar">
      <LanguageSwitcher />
    </div>

    <form class="login-card" @submit.prevent="submit">
      <img src="../assets/logo/werwolf-icon.svg" alt="Werwolf Media" class="login-logo" />
      <div class="login-brand">
        <span class="login-title-text">MIROFISH</span>
        <span class="login-byline">by Werwolf Media</span>
      </div>

      <h1 class="login-headline">{{ $t('login.title') }}</h1>
      <p class="login-subtitle">{{ $t('login.subtitle') }}</p>

      <input
        ref="pwInput"
        v-model="password"
        type="password"
        class="login-input"
        :placeholder="$t('login.passwordPlaceholder')"
        :disabled="loading"
        autocomplete="current-password"
        autofocus
      />

      <p v-if="error" class="login-error">{{ $t('login.error') }}</p>

      <button class="login-btn" type="submit" :disabled="loading || !password">
        <span v-if="!loading">{{ $t('login.submit') }}</span>
        <span v-else>{{ $t('login.submitting') }}</span>
        <span class="login-arrow">→</span>
      </button>
    </form>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { login } from '../store/auth'
import LanguageSwitcher from './LanguageSwitcher.vue'

const password = ref('')
const loading = ref(false)
const error = ref(false)
const pwInput = ref(null)

onMounted(() => {
  pwInput.value?.focus()
})

const submit = async () => {
  if (loading.value || !password.value) return
  error.value = false
  loading.value = true
  try {
    const ok = await login(password.value)
    if (!ok) {
      error.value = true
      password.value = ''
    }
    // bei Erfolg aktualisiert sich der Auth-Store -> App.vue blendet das Overlay aus
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: #000000;
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: 'JetBrains Mono', 'Space Grotesk', monospace;
}

.login-topbar {
  position: absolute;
  top: 20px;
  right: 24px;
}

.login-card {
  width: 100%;
  max-width: 360px;
  padding: 0 24px;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.login-logo {
  height: 56px;
  width: auto;
  filter: brightness(0) invert(1);
  margin-bottom: 16px;
}

.login-brand {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 36px;
}

.login-title-text {
  font-weight: 800;
  letter-spacing: 2px;
  font-size: 1.4rem;
}

.login-byline {
  font-size: 0.72rem;
  opacity: 0.55;
  padding-left: 10px;
  border-left: 1px solid rgba(255, 255, 255, 0.25);
}

.login-headline {
  font-size: 1.1rem;
  font-weight: 600;
  margin-bottom: 6px;
}

.login-subtitle {
  font-size: 0.82rem;
  opacity: 0.6;
  margin-bottom: 24px;
  line-height: 1.4;
}

.login-input {
  width: 100%;
  padding: 14px 16px;
  background: #111111;
  border: 1px solid #333333;
  border-radius: 8px;
  color: #ffffff;
  font-family: inherit;
  font-size: 0.95rem;
  outline: none;
  transition: border-color 0.2s;
}

.login-input:focus {
  border-color: var(--orange, #ff6b2c);
}

.login-input:disabled {
  opacity: 0.5;
}

.login-error {
  color: #ff5a5a;
  font-size: 0.8rem;
  margin-top: 10px;
  align-self: flex-start;
}

.login-btn {
  width: 100%;
  margin-top: 20px;
  padding: 14px 16px;
  background: var(--orange, #ff6b2c);
  color: #ffffff;
  border: none;
  border-radius: 8px;
  font-family: inherit;
  font-weight: 700;
  font-size: 0.95rem;
  letter-spacing: 0.5px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  transition: opacity 0.2s, transform 0.05s;
}

.login-btn:hover:not(:disabled) {
  opacity: 0.9;
}

.login-btn:active:not(:disabled) {
  transform: translateY(1px);
}

.login-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.login-arrow {
  font-weight: 400;
}
</style>
