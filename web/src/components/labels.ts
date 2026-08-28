// 领域术语中文标签（单处维护，组件共用）：雪花七层 + 提案 kind + 灵感面板
import type { LayerKind, ProposalKind } from '../types'

export const LAYERS: LayerKind[] = [
  'premise', 'synopsis', 'summary', 'beat_sheet',
  'characters', 'scenes', 'prose',
]

export const LAYER_LABELS: Record<LayerKind, string> = {
  premise: '前提',
  synopsis: '梗概',
  summary: '摘要',
  beat_sheet: '节拍表',
  characters: '角色',
  scenes: '场景',
  prose: '正文',
}

// 生成环 artifact_type 与 LAYERS 同构（generate.py ARTIFACTS 键）
export const ARTIFACT_LABELS = LAYER_LABELS

export const KIND_LABELS: Record<ProposalKind, string> = {
  premise: '前提',
  synopsis: '梗概',
  summary: '摘要',
  beat_sheet: '节拍表',
  characters: '角色',
  scene: '场景',
  prose: '正文',
  microbeat_group: '微节拍组',
  chapter_intent: '章意图',
  volume_theme: '卷主题',
  volume_acts: '卷三幕',
  retcon: '回溯变更',
  foreshadow: '伏笔',
  revision: '修订',
  extract_facts: '事实抽取',
}

// 灵感面板（TC-SH-09 / R4）：面板标题/输入/按钮 + GenerateForm derive 小节标题
export const INSPIRATION_LABELS = {
  panelTitle: '灵感',
  input: '灵感原话',
  save: '保存灵感',
  derive: '从灵感发起生成',
} as const

// 拍侧栏（TC-SH-10 / R5）：ProseEditor 章编辑区拍列表 + 合并/删除操作文案
export const BEAT_LABELS = {
  panelTitle: '拍',
  merge: '合并',
  delete: '删除',
  mergeInto: '并入此拍',
  pickTarget: '点选合并目标拍',
  cancelMerge: '取消合并',
  sourceBeat: '源拍',
  empty: '本章暂无拍',
  noForeshadow: '无伏笔引用此拍',
} as const

// 手册弹窗（TC-SH-13 / R3）：顶栏"？"入口 + 弹窗内文案
export const MANUAL_LABELS = {
  openBtn: '使用手册',
  filter: '过滤手册',
  filterPlaceholder: '输入关键词过滤章节…',
  toc: '手册目录',
  empty: '没有匹配的章节',
  close: '关闭手册',
  restartTour: '重看操作导览',
} as const

// 操作指引 tour（TC-SH-14 / R2+R4+R7）：欢迎卡与气泡按钮词 + 六步定稿文案。
// 六步含 target testid（Tour.tsx 在 document 里查元素做高亮，缺失时气泡兜底定位）；
// 第 5/6 步文案按 R7 提及 readonly / 保存与租约要点。
export const TOUR_LABELS = {
  welcomeTitle: '欢迎来到 Snowel',
  welcomeBody: '用 1 分钟走一遍三栏工作台，随时可在"？"手册里重新开始导览。',
  start: '开始导览',
  skip: '跳过',
  prev: '上一步',
  next: '下一步',
  exit: '退出',
  finish: '完成',
} as const

export const TOUR_STEPS: readonly {
  testid: string
  title: string
  body: string
}[] = [
  {
    testid: 'app-main',
    title: '三栏布局',
    body: '左侧流程树、中间正文、右侧工作区与聊天——整个创作台就是这三块。',
  },
  {
    testid: 'col-flow',
    title: '流程树',
    body: '雪花五层流程的进度与待办都在这里；点击章节点，中间与右栏会跟着联动选中。',
  },
  {
    testid: 'generate-form',
    title: '生成表单',
    body: '从选中的节点发起生成：七类 artifact 任选，也可以从灵感原话派生生成。',
  },
  {
    testid: 'proposal-panel',
    title: '提案确认',
    body: '生成结果先入提案队列；这个结构化面板是唯一确认口——确认 / 否决 / 改写都在这里完成。',
  },
  {
    testid: 'prose-editor',
    title: '正文编辑',
    body: '确认后的正文在此编辑润色；注意及时保存。只读（readonly）会话下仅可浏览不可改动。',
  },
  {
    testid: 'chat-sidebar',
    title: '聊天侧栏',
    body: '与 AI 对话即可发起生成或检索；写租约被其他端持有时本端降级只读，待心跳续租收回后再写。',
  },
] as const
