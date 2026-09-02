<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { api } from './api'

const tabs = [['status', '概览'], ['search', '搜索'], ['duplicates', '重复文件'], ['settings', '设置']]
const active = ref('status')
const busy = ref(false)
const message = ref('')
const error = ref('')
const status = reactive({ work_dir: '', dirs: 0, files: 0, size: 0, updated: '' })
const progress = reactive({ progress: 100, cur_path: '', speed: 0 })
const tags = ref('')
const searchItems = ref([])
const searchPage = ref(0)
const duplicateItems = ref([])
const onlyDirs = ref(false)
const selected = ref(new Set())
const settings = reactive({ work_dir: '', quick_hash_size: '0', scan_interval: 86400 })
let progressTimer

const scanning = computed(() => Number(progress.progress) < 100)
const groupedDuplicates = computed(() => {
  const groups = new Map()
  duplicateItems.value.forEach(item => {
    if (!groups.has(item.fhash)) groups.set(item.fhash, [])
    groups.get(item.fhash).push(item)
  })
  return groups
})
const duplicateRows = computed(() => {
  const indexes = new Map()
  let nextIndex = 0
  return duplicateItems.value.map(item => {
    if (!indexes.has(item.fhash)) indexes.set(item.fhash, nextIndex++)
    return { ...item, groupIndex: indexes.get(item.fhash) }
  })
})

function notify(text, isError = false) {
  if (isError) error.value = text
  else message.value = text
  window.setTimeout(() => { message.value = ''; error.value = '' }, 3500)
}

async function loadStatus() {
  try { Object.assign(status, await api.status()) } catch (e) { notify(e.message, true) }
}

async function pollProgress() {
  window.clearTimeout(progressTimer)
  try {
    Object.assign(progress, await api.progress())
    if (scanning.value) progressTimer = window.setTimeout(pollProgress, 1000)
    else await loadStatus()
  } catch (e) { notify(e.message, true) }
}

async function startScan() {
  busy.value = true
  try {
    const result = await api.startScan()
    notify(result.message)
    progress.progress = 0
    progressTimer = window.setTimeout(pollProgress, 500)
  } catch (e) { notify(e.message, true) }
  finally { busy.value = false }
}

async function runSearch(append = false) {
  if (!tags.value.trim()) return notify('请输入标签', true)
  busy.value = true
  try {
    const page = append ? searchPage.value + 1 : 0
    const result = await api.search(tags.value.trim(), page)
    searchItems.value = append ? searchItems.value.concat(result.items) : result.items
    searchPage.value = page
  } catch (e) { notify(e.message, true) }
  finally { busy.value = false }
}

async function loadDuplicates() {
  busy.value = true
  try {
    duplicateItems.value = (await api.duplicates(0, onlyDirs.value)).items
    selected.value = new Set()
  } catch (e) { notify(e.message, true) }
  finally { busy.value = false }
}

function selectCopies(keepFirst) {
  const next = new Set()
  groupedDuplicates.value.forEach(group => group.forEach((item, index) => {
    if (index !== (keepFirst ? 0 : group.length - 1)) next.add(item.id)
  }))
  selected.value = next
}

function toggle(id) {
  const next = new Set(selected.value)
  next.has(id) ? next.delete(id) : next.add(id)
  selected.value = next
}

async function removeOne(id) {
  if (!window.confirm('确定删除磁盘上的这个文件及其数据库记录？')) return
  try {
    const target = duplicateItems.value.find(item => item.id === id)
    const targetHash = target?.fhash
    await api.deleteDuplicate(id)
    if (!target) {
      duplicateItems.value = duplicateItems.value.filter(item => item.id !== id)
      notify('删除成功')
      return
    }
    const remainingInGroup = duplicateItems.value.filter(
      item => item.fhash === targetHash && item.id !== id
    )
    duplicateItems.value = remainingInGroup.length < 2
      ? duplicateItems.value.filter(item => item.fhash !== targetHash)
      : duplicateItems.value.filter(item => item.id !== id)
    notify('删除成功')
  } catch (e) { notify(e.message, true) }
}

async function removeSelected() {
  if (!selected.value.size || !window.confirm(`确定删除选中的 ${selected.value.size} 项？`)) return
  busy.value = true
  for (const id of [...selected.value]) {
    try { await api.deleteDuplicate(id) } catch (e) { notify(e.message, true); break }
  }
  busy.value = false
  await loadDuplicates()
}

async function loadSettings() {
  try { Object.assign(settings, await api.settings()) } catch (e) { notify(e.message, true) }
}

async function saveSettings(confirm = false) {
  try {
    const result = await api.saveSettings({ ...settings, confirm })
    if (result.confirm === 'required') {
      if (window.confirm('扫描目录已改变。应用后，下次扫描会重建索引（不会直接删除磁盘文件），是否继续？')) return saveSettings(true)
      return
    }
    notify('设置已保存')
    await loadStatus()
  } catch (e) { notify(e.message, true) }
}

watch(active, value => {
  if (value === 'duplicates' && !duplicateItems.value.length) loadDuplicates()
  if (value === 'settings') loadSettings()
})
watch(onlyDirs, loadDuplicates)
onMounted(async () => {
  await loadSettings()
  if (!settings.work_dir) active.value = 'settings'
  await Promise.all([loadStatus(), pollProgress()])
})
onBeforeUnmount(() => window.clearTimeout(progressTimer))
</script>

<template>
  <div class="shell">
    <header><div class="brand"><img class="brand-logo" src="/logo.png" alt="Diskr.space" /><small>文件索引与去重</small></div></header>
    <nav><button v-for="tab in tabs" :key="tab[0]" :class="{ active: active === tab[0] }" @click="active = tab[0]">{{ tab[1] }}</button></nav>
    <main>
      <section v-if="active === 'status'">
        <div class="heading"><div><p class="eyebrow">SYSTEM OVERVIEW</p><h1>存储概览</h1></div><button class="primary" :disabled="busy || scanning" @click="startScan">{{ scanning ? '扫描中…' : '立即扫描' }}</button></div>
        <div v-if="scanning" class="scan-card"><div class="progress"><i :style="{ width: `${progress.progress}%` }"></i></div><p>{{ progress.progress }}% · {{ progress.speed }} 项/秒</p><small>{{ progress.cur_path || '正在准备扫描…' }}</small></div>
        <div class="stats"><article><span>文件</span><strong>{{ status.files || 0 }}</strong></article><article><span>目录</span><strong>{{ status.dirs || 0 }}</strong></article><article><span>占用空间</span><strong>{{ status.size || 0 }}</strong></article></div>
        <div class="card details"><div><span>扫描目录</span><b>{{ status.work_dir }}</b></div><div><span>上次完成</span><b>{{ status.updated || '尚未扫描' }}</b></div></div>
      </section>

      <section v-else-if="active === 'search'">
        <div class="heading"><div><p class="eyebrow">TAG INDEX</p><h1>文件搜索</h1></div></div>
        <form class="searchbar" @submit.prevent="runSearch(false)"><input v-model="tags" placeholder="输入标签，空格或逗号分隔" /><button class="primary" :disabled="busy">搜索</button></form>
        <div class="card table-wrap"><table><thead><tr><th>路径</th><th>大小</th><th>修改时间</th></tr></thead><tbody><tr v-for="item in searchItems" :key="item.id"><td>{{ item.name }}</td><td>{{ item.ftype === 'D' ? '目录 · ' : '' }}{{ item.size }}</td><td>{{ item.ftime }}</td></tr><tr v-if="!searchItems.length"><td colspan="3" class="empty">暂无结果</td></tr></tbody></table></div>
        <button v-if="searchItems.length === 50" class="secondary more" @click="runSearch(true)">加载更多</button>
      </section>

      <section v-else-if="active === 'duplicates'">
        <div class="heading"><div><p class="eyebrow">HASH MATCHES</p><h1>重复文件</h1></div><button class="secondary" :disabled="busy" @click="loadDuplicates">刷新</button></div>
        <div class="toolbar"><label><input v-model="onlyDirs" type="checkbox" /> 仅目录</label><button @click="selectCopies(true)">保留每组第一项</button><button @click="selectCopies(false)">保留每组最后一项</button><button class="danger" :disabled="!selected.size" @click="removeSelected">删除所选 ({{ selected.size }})</button></div>
        <div class="card table-wrap"><table><thead><tr><th></th><th>路径</th><th>大小</th><th>修改时间</th><th></th></tr></thead><tbody><tr v-for="item in duplicateRows" :key="item.id" :class="{ 'duplicate-alt': item.groupIndex % 2 === 1 }"><td><input type="checkbox" :checked="selected.has(item.id)" @change="toggle(item.id)" /></td><td>{{ item.name }}</td><td>{{ item.size }}</td><td>{{ item.ftime }}</td><td><button class="icon danger-text" @click="removeOne(item.id)">删除</button></td></tr><tr v-if="!duplicateItems.length"><td colspan="5" class="empty">没有发现重复项</td></tr></tbody></table></div>
      </section>

      <section v-else>
        <div class="heading"><div><p class="eyebrow">CONFIGURATION</p><h1>扫描设置</h1></div><button class="primary" @click="saveSettings(false)">保存设置</button></div>
        <div class="card form"><label>扫描目录<input v-model="settings.work_dir" /></label><label>快速 Hash 大小<input v-model="settings.quick_hash_size" placeholder="0 / 4M / 1G" /><small>0 表示计算全文件 Hash，也可使用 K、M、G。</small></label><label>完整扫描间隔（秒）<input v-model.number="settings.scan_interval" type="number" min="0" /></label></div>
      </section>
    </main>
    <div v-if="message" class="toast">{{ message }}</div><div v-if="error" class="toast error">{{ error }}</div>
  </div>
</template>
