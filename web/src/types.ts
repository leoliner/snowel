// 与后端响应一比一的类型面（web_server.py + core api 门面）

// 雪花七层（flow/state.py LAYERS）
export type LayerKind =
  | 'premise'
  | 'synopsis'
  | 'summary'
  | 'beat_sheet'
  | 'characters'
  | 'scenes'
  | 'prose'

export interface Chapter {
  id: string
  name: string
}

export interface Volume {
  id: string
  name: string
  chapters: Chapter[]
}

// GET /api/session → flow 字段（flow_state()）
export interface FlowState {
  layers: Record<LayerKind, 'done' | 'todo'>
  current_layer: LayerKind | null
  volumes: Volume[]
}

// GET /api/session
export interface Session {
  project: string
  readonly: boolean
  holder: string | null
  flow: FlowState
}

// 提案 kind（flow/registry.py ARTIFACTS + retcon/foreshadow/revision/extract_facts 等）
export type ProposalKind =
  | 'premise'
  | 'synopsis'
  | 'summary'
  | 'beat_sheet'
  | 'characters'
  | 'scene'
  | 'prose'
  | 'microbeat_group'
  | 'chapter_intent'
  | 'volume_theme'
  | 'volume_acts'
  | 'retcon'
  | 'foreshadow'
  | 'revision'
  | 'extract_facts'

export type ProposalStatus = 'pending' | 'stale' | 'confirmed' | 'rejected' | 'voided'

// GET /api/proposals：行 + 解析后的 payload（web_server._proposal）
export interface Proposal {
  id: string
  kind: ProposalKind
  status: ProposalStatus
  payload: Record<string, unknown>
  stale_hint?: string | null
}

export type ViolationLevel = 'major' | 'minor'

// 级联违规 detail：矛盾项 diff 三元组（consistency/rules.py contradiction）
export interface ViolationDetail {
  node_id?: string
  key?: string
  old?: unknown
  new?: unknown
}

// 级联检查违规（consistency/engine.py）
export interface Violation {
  level: ViolationLevel
  rule: string
  message: string
  refs: string[]
  detail?: ViolationDetail
}

// 确认/预演响应（wiring.preview / finalize）：violations + major 矛盾 diff 条目
export interface DiffEntry extends ViolationDetail {
  refs?: string[]
}
export interface CascadePreviewResult {
  tier: string
  violations: Violation[]
  diff_preview: DiffEntry[]
}
export interface CascadeResult {
  tier: string
  violations: Violation[]
  cascade_proposal_id: string | null
}

// POST /api/proposals/{pid}/confirm(confirm_retcon) → seq + 最近级联
export interface ConfirmResult {
  seq: number
  cascade: CascadeResult | null
}

// GET /api/reconcile：正文镜像对账（changed/missing 清单，status 见 mirror.py）
export interface ReconcileEntry {
  chapter_id: string
  status: string
}

export interface GenerateResult {
  proposal_id: string
}

export interface RewriteResult {
  proposal_id: string
}

// 聊天 SSE 事件（llm/chat.py + web_server 流内 error）
export interface ToolCallEvent {
  type: 'tool_call'
  tool: string
  args: Record<string, unknown>
}
export interface ToolResultEvent {
  type: 'tool_result'
  tool: string
  ok: boolean
  summary: string
}
export interface ReplyEvent {
  type: 'reply'
  text: string
}
export interface DoneEvent {
  type: 'done'
  proposal_ids: string[]
}
export interface ErrorEvent {
  type: 'error'
  text: string
}

export type ChatEvent = ToolCallEvent | ToolResultEvent | ReplyEvent | DoneEvent | ErrorEvent

// ---- GET /api/stats/*（T7 W4 统计四件，与后端 queries.py 形状一比一）----

// GET /api/stats/pov：分卷 POV 频次（volume_id/name 为 null = 无 address 的未分卷聚合）
export interface PovVolumeStat {
  volume_id: string | null
  volume_name: string | null
  counts: Record<string, number>
}
export interface PovStatsResponse {
  by_volume: PovVolumeStat[]
}

// GET /api/stats/foreshadow：伏笔清单（planted_at/payoff_beat 为拍节点 id；
// status 口径：payoff 未设=planted / 目标活跃=paid / 目标缺失或撤回=stale）
export type ForeshadowStatus = 'planted' | 'paid' | 'stale'
export interface ForeshadowItem {
  id: string
  name: string
  planted_at: string | null
  payoff_beat: string | null
  status: ForeshadowStatus
}
export interface ForeshadowStatsResponse {
  items: ForeshadowItem[]
}

// GET /api/stats/relations：活跃 Character 节点 + 两端均活跃的边（行序列化）
export interface RelationNode {
  id: string
  types: string
  name: string
  props: Record<string, unknown>
  active: number
}
export interface RelationEdge {
  id: string
  src: string
  dst: string
  kind: string
  props: Record<string, unknown>
}
export interface RelationsStatsResponse {
  nodes: RelationNode[]
  edges: RelationEdge[]
}

// GET /api/stats/pacing：每章拍数（地址聚合）与段落数（镜像段落行计数）
export interface PacingChapter {
  chapter_id: string
  name: string
  beats: number
  paragraphs: number
}
export interface PacingStatsResponse {
  chapters: PacingChapter[]
}
