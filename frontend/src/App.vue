<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { api } from './api'

const tabs = [['status', '概览'], ['search', '搜索'], ['duplicates', '重复文件'], ['settings', '设置']]
const active = ref('status')
const busy = ref(false)
const searching = ref(false)
const message = ref('')
const error = ref('')
const status = reactive({ work_dir: '', dirs: 0, files: 0, size: 0, updated: '' })
const progress = reactive({ progress: 100, cur_path: '', speed: 0 })
const tags = ref('')
const searchItems = ref([])
const searchPage = ref(0)
const searchTotal = ref(0)
const searchPageSize = ref(50)
const searched = ref(false)
const duplicateItems = ref([])
const duplicatesLoading = ref(false)
const duplicatePage = ref(0)
const duplicateTotal = ref(0)
const savedDuplicatePageSize = Number.parseInt(window.localStorage.getItem('diskrspace.duplicatePageSize'), 10)
const duplicatePageSize = ref([50, 200].includes(savedDuplicatePageSize) ? savedDuplicatePageSize : 50)
const onlyDirs = ref(true)
const selected = ref(new Set())
const deleting = ref(false)
const deletingName = ref('')
const deleteErrorDetails = ref([])
const settings = reactive({ work_dir: '', quick_hash_size: '0', scan_interval: 86400 })
let progressTimer
const duplicatesCache = new Map()
const duplicatesPending = new Map()

const scanning = computed(() => Number(progress.progress) < 100)
const sizeDisplay = computed(() => {
  const match = String(status.size ?? '').match(/^(.*?[KMGT])\((-?\d+)\)$/)
  if (!match) return { main: status.size || 0, raw: '' }
  return { main: match[1], raw: Number(match[2]).toLocaleString('en-US') }
})
function formatCount(value) {
  return Number(value || 0).toLocaleString('en-US')
}
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
    const wasScanning = scanning.value
    Object.assign(progress, await api.progress())
    await loadStatus()
    if (scanning.value) progressTimer = window.setTimeout(pollProgress, 1000)
    else if (wasScanning && active.value === 'duplicates') await loadDuplicates(duplicatePage.value, true)
  } catch (e) {
    notify(e.message, true)
    if (scanning.value) progressTimer = window.setTimeout(pollProgress, 1000)
  }
}

async function startScan() {
  busy.value = true
  try {
    const result = await api.startScan()
    notify(result.message)
    if (settings.work_dir.trim() !== status.work_dir.trim()) {
      status.files = 0
      status.dirs = 0
      status.size = 0
      status.updated = ''
    }
    progress.progress = 0
    progressTimer = window.setTimeout(pollProgress, 500)
  } catch (e) { notify(e.message, true) }
  finally { busy.value = false }
}

async function stopScan() {
  if (!window.confirm('确定中断当前扫描？已写入的数据会保留。')) return
  busy.value = true
  try {
    await api.stopScan()
    window.clearTimeout(progressTimer)
    progress.progress = 100
    await loadStatus()
    notify('扫描已中断')
  } catch (e) { notify(e.message, true) }
  finally { busy.value = false }
}

async function runSearch(page = 0) {
  if (!tags.value.trim()) return notify('请输入标签', true)
  busy.value = true
  searching.value = true
  try {
    const result = await api.search(tags.value.trim(), page)
    searchItems.value = result.items
    searchPage.value = result.page
    searchTotal.value = result.total
    searchPageSize.value = result.page_size
    searched.value = true
  } catch (e) { notify(e.message, true) }
  finally { searching.value = false; busy.value = false }
}

async function loadDuplicates(page = duplicatePage.value, force = false) {
  const cacheKey = `${onlyDirs.value ? 'dirs' : 'all'}:${duplicatePageSize.value}:${page}`
  if (duplicatesPending.has(cacheKey)) {
    await duplicatesPending.get(cacheKey)
    return
  }
  if (!force && duplicatesCache.has(cacheKey)) {
    const cached = duplicatesCache.get(cacheKey)
    duplicateItems.value = [...cached.items]
    duplicatePage.value = page
    duplicateTotal.value = cached.total
    duplicatePageSize.value = cached.pageSize
    selected.value = new Set()
    return
  }
  busy.value = true
  duplicatesLoading.value = true
  const request = api.duplicates(0, onlyDirs.value, page, duplicatePageSize.value)
  duplicatesPending.set(cacheKey, request)
  try {
    const result = await request
    duplicateItems.value = result.items
    duplicatePage.value = result.page
    duplicateTotal.value = result.total
    duplicatePageSize.value = result.page_size
    if (!result.scanning) {
      duplicatesCache.set(cacheKey, {
        items: [...duplicateItems.value], total: result.total, pageSize: result.page_size,
      })
    }
    selected.value = new Set()
  } catch (e) { notify(e.message, true) }
  finally {
    duplicatesPending.delete(cacheKey)
    duplicatesLoading.value = false
    busy.value = false
  }
}

async function refreshDuplicates() {
  duplicateItems.value = []
  duplicateTotal.value = 0
  duplicatesLoading.value = true
  try { await loadDuplicates(duplicatePage.value, true) }
  finally { duplicatesLoading.value = false }
}

async function changeDuplicatePageSize() {
  duplicatePage.value = 0
  duplicateItems.value = []
  duplicateTotal.value = 0
  duplicatesCache.clear()
  await loadDuplicates(0, true)
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
    deleting.value = true
    deletingName.value = target?.name || `记录 #${id}`
    const targetHash = target?.fhash
    await api.deleteDuplicate(id)
    if (!target) {
      duplicateItems.value = duplicateItems.value.filter(item => item.id !== id)
      await refreshDuplicates()
      notify('删除成功')
      return
    }
    const remainingInGroup = duplicateItems.value.filter(
      item => item.fhash === targetHash && item.id !== id
    )
    duplicateItems.value = remainingInGroup.length < 2
      ? duplicateItems.value.filter(item => item.fhash !== targetHash)
      : duplicateItems.value.filter(item => item.id !== id)
    duplicatesCache.clear()
    selected.value = new Set()
    await refreshDuplicates()
    notify('删除成功')
  } catch (e) { notify(e.message, true) }
  finally { deleting.value = false; deletingName.value = '' }
}

async function removeSelected() {
  if (!selected.value.size || !window.confirm(`确定删除选中的 ${selected.value.size} 项？`)) return
  busy.value = true
  deleting.value = true
  deleteErrorDetails.value = []
  const failures = []
  let deletedCount = 0
  try {
    for (const id of [...selected.value]) {
      const item = duplicateItems.value.find(entry => entry.id === id)
      deletingName.value = item?.name || `记录 #${id}`
      try {
        await api.deleteDuplicate(id)
        deletedCount += 1
      } catch (e) {
        failures.push(`${deletingName.value}: ${e.message}`)
      }
    }
  } finally {
    deleting.value = false
    deletingName.value = ''
  }
  selected.value = new Set()
  busy.value = false
  duplicatesCache.clear()
  await refreshDuplicates()
  if (failures.length) {
    deleteErrorDetails.value = failures
  } else {
    notify(`已删除 ${deletedCount} 项`)
  }
}

function closeDeleteErrors() {
  deleteErrorDetails.value = []
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
    // Keep the overview in sync immediately, even when the user switches tabs
    // before the next status refresh.
    status.work_dir = settings.work_dir
    await loadStatus()
  } catch (e) { notify(e.message, true) }
}

watch(active, value => {
  if (value === 'status') { loadStatus(); pollProgress() }
  if (value === 'duplicates') {
    const cacheKey = `${onlyDirs.value ? 'dirs' : 'all'}:${duplicatePageSize.value}:${duplicatePage.value}`
    if (!duplicatesCache.has(cacheKey)) {
      duplicateItems.value = []
      duplicateTotal.value = 0
      loadDuplicates()
    }
  }
  if (value === 'settings') loadSettings()
})
watch(onlyDirs, async () => {
  duplicatePage.value = 0
  duplicateItems.value = []
  duplicateTotal.value = 0
  duplicatesLoading.value = true
  await loadDuplicates(0)
  duplicatesLoading.value = false
})
watch(duplicatePageSize, value => {
  window.localStorage.setItem('diskrspace.duplicatePageSize', String(value))
})
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
        <div v-if="scanning" class="scan-card"><div class="progress-row"><div class="progress"><i :style="{ width: `${progress.progress}%` }"></i></div><button class="stop-scan" :disabled="busy" title="中断扫描" aria-label="中断扫描" @click="stopScan">×</button></div><p>{{ progress.progress }}% · {{ progress.speed }} 项/秒</p><small>{{ progress.cur_path || '正在准备扫描…' }}</small></div>
        <div class="stats"><article><span>文件</span><strong>{{ formatCount(status.files) }}</strong></article><article><span>目录</span><strong>{{ formatCount(status.dirs) }}</strong></article><article><span>占用空间</span><strong><span class="size-main">{{ sizeDisplay.main }}</span><small v-if="sizeDisplay.raw" class="size-raw">({{ sizeDisplay.raw }})</small></strong></article></div>
        <div class="card details"><div><span>扫描目录</span><b>{{ status.work_dir }}</b></div><div><span>上次完成</span><b>{{ status.updated || '尚未扫描' }}</b></div></div>
      </section>

      <section v-else-if="active === 'search'">
        <div class="heading"><div><p class="eyebrow">TAG INDEX</p><h1>文件搜索</h1></div></div>
        <form class="searchbar" @submit.prevent="runSearch(0)"><input v-model="tags" :disabled="searching" placeholder="输入标签，空格或逗号分隔" /><button class="primary" :disabled="busy"><span v-if="searching" class="loading-dot" aria-hidden="true"></span>{{ searching ? '搜索中…' : '搜索' }}</button></form>
        <p v-if="searching" class="loading-hint" role="status">正在查询大量文件，请稍候…</p>
        <div class="card table-wrap"><table><thead><tr><th>路径</th><th>大小</th><th>修改时间</th></tr></thead><tbody><tr v-for="item in searchItems" :key="item.id"><td>{{ item.name }}</td><td>{{ item.ftype === 'D' ? '目录 · ' : '' }}{{ item.size }}</td><td>{{ item.ftime }}</td></tr><tr v-if="!searchItems.length"><td colspan="3" class="empty">暂无结果</td></tr></tbody></table></div>
        <div v-if="searched" class="search-pagination"><span>共 {{ searchTotal.toLocaleString('en-US') }} 条结果</span><template v-if="searchTotal"><button class="secondary" :disabled="busy || searchPage === 0" @click="runSearch(searchPage - 1)">上一页</button><span>第 {{ searchPage + 1 }} / {{ Math.ceil(searchTotal / searchPageSize) }} 页</span><button class="secondary" :disabled="busy || (searchPage + 1) * searchPageSize >= searchTotal" @click="runSearch(searchPage + 1)">下一页</button></template></div>
      </section>

      <section v-else-if="active === 'duplicates'">
        <div class="heading"><div><p class="eyebrow">HASH MATCHES</p><h1>重复文件</h1></div><button class="secondary" :disabled="busy" @click="loadDuplicates(duplicatePage, true)">刷新</button></div>
        <div class="toolbar"><label><input v-model="onlyDirs" type="checkbox" /> 仅目录</label><label class="page-size-label">每页 <select v-model.number="duplicatePageSize" :disabled="busy" @change="changeDuplicatePageSize"><option :value="50">50 项</option><option :value="200">200 项</option></select></label><button @click="selectCopies(true)">保留每组第一项</button><button @click="selectCopies(false)">保留每组最后一项</button><button class="danger" :disabled="busy || !selected.size" @click="removeSelected">{{ deleting ? '删除中…' : `删除所选 (${selected.size})` }}</button></div>
        <div class="card table-wrap"><table class="duplicates-table"><thead><tr><th></th><th>路径</th><th>大小</th><th>修改时间</th><th></th></tr></thead><tbody><tr v-for="item in duplicateRows" :key="item.id" :class="{ 'duplicate-alt': item.groupIndex % 2 === 1 }"><td><input type="checkbox" :checked="selected.has(item.id)" @change="toggle(item.id)" /></td><td><span class="path-cell" :title="item.name">{{ item.name }}</span></td><td>{{ item.size }}</td><td>{{ item.ftime }}</td><td><button class="icon danger-text" @click="removeOne(item.id)">删除</button></td></tr><tr v-if="duplicatesLoading"><td colspan="5" class="empty"><span class="loading-dot dark" aria-hidden="true"></span>正在查询重复文件，请稍候…</td></tr><tr v-else-if="!duplicateItems.length"><td colspan="5" class="empty">没有发现重复项</td></tr></tbody></table></div>
        <div v-if="duplicateTotal" class="search-pagination"><span>共 {{ duplicateTotal.toLocaleString('en-US') }} 条结果</span><button class="secondary" :disabled="busy || duplicatePage === 0" @click="loadDuplicates(duplicatePage - 1)">上一页</button><span>第 {{ duplicatePage + 1 }} / {{ Math.ceil(duplicateTotal / duplicatePageSize) }} 页</span><button class="secondary" :disabled="busy || (duplicatePage + 1) * duplicatePageSize >= duplicateTotal" @click="loadDuplicates(duplicatePage + 1)">下一页</button></div>
      </section>

      <section v-else>
        <div class="heading"><div><p class="eyebrow">CONFIGURATION</p><h1>扫描设置</h1></div><button class="primary" @click="saveSettings(false)">保存设置</button></div>
        <div class="card form"><label>扫描目录<input v-model="settings.work_dir" /></label><label>快速 Hash 大小<input v-model="settings.quick_hash_size" placeholder="0 / 4M / 1G" /><small>0 表示计算全文件 Hash，也可使用 K、M、G。</small></label><label>完整扫描间隔（秒）<input v-model.number="settings.scan_interval" type="number" min="0" /></label></div>
      </section>
    </main>
    <div v-if="deleting" class="modal-backdrop"><div class="delete-modal" role="status" aria-live="polite"><span class="modal-spinner" aria-hidden="true"></span><strong>正在删除</strong><p>{{ deletingName }}</p><small>请稍候，删除完成后窗口会自动关闭</small></div></div>
    <div v-if="deleteErrorDetails.length" class="modal-backdrop"><div class="delete-modal delete-error-modal" role="alert"><strong>部分文件删除失败</strong><p v-for="(detail, index) in deleteErrorDetails" :key="index">{{ detail }}</p><button class="primary" @click="closeDeleteErrors">确认</button></div></div>
    <div v-if="message" class="toast">{{ message }}</div><div v-if="error" class="toast error">{{ error }}</div>
  </div>
</template>
