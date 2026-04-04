export interface User {
  id: number
  telegram_user_id: number
  first_name: string
  username?: string | null
  status: string
}

export interface Citation {
  doc_name: string
  section: string
  page: number
  visual_url?: string | null
}

export interface QueryResponse {
  answer: string
  citations: Citation[]
  model_used: string
  no_answer: boolean
  retrieval_score: number
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  query_id?: string | null
  response?: QueryResponse | null
  created_at: string
}

export interface Session {
  id: string
  user_id: number
  machine_model: string
  title?: string | null
  status: 'active' | 'paused' | 'completed'
  created_at?: string | null
  updated_at?: string | null
}
