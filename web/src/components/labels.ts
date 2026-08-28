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
