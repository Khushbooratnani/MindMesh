export type ScreenId =
  | 'welcome'
  | 'login'
  | 'signup'
  | 'forgot_password'
  | 'home'
  | 'composer'
  | 'memory_detail'
  | 'vault'
  | 'locker'
  | 'groups'
  | 'group_detail';

export type MemoryType = 'note' | 'photo' | 'voice' | 'receipt' | 'location';
export type MediaType = 'text' | 'image' | 'audio';
export type Privacy = 'ONLY_ME' | 'GROUP' | 'SELECTED' | 'PRIVATE_LOCKER';
export type Sentiment = 'positive' | 'neutral' | 'negative' | 'mixed' | 'unknown';
export type TimeOfDay = 'morning' | 'afternoon' | 'evening' | 'night' | 'unknown';

export interface SystemFields {
  owner_id: string;
  group_id?: string | null;
  media_type: MediaType;
  created_at: string;
  privacy: Privacy;
  allowed_users: string[];
}

export interface ContentFields {
  raw_text?: string | null;
  clean_text: string;
  description: string;
  summary: string;
  user_context?: string | null;
}

export interface EntityFields {
  people: string[];
  places: string[];
  locations: string[];
  events: string[];
  organizations: string[];
}

export interface SemanticFields {
  topics: string[];
  activities: string[];
  sentiment: Sentiment;
  mood: string[];
}

export interface TemporalFields {
  mentioned_dates: string[];
  inferred_time?: string | null;
  time_of_day?: TimeOfDay | null;
}

export interface MediaReference {
  storage_key: string;
  relative_path: string;
  original_filename: string;
  media_type: string;
  content_type?: string | null;
  size_bytes: number;
  sha256: string;
  created_at?: string | null;
}

export interface AdditionalAttribute {
  key: string;
  value: any;
  confidence: number;
  source: 'llm' | 'system' | 'user';
}

export interface ProcessingFields {
  status: 'completed' | 'failed' | 'partial';
  source_modality: MediaType;
  transcription_required: boolean;
  image_understanding_required: boolean;
  llm_provider: string;
  llm_model: string;
  errors: string[];
}

export interface MemoryV1 {
  memory_id: string;
  schema_version: '1.0';
  system: SystemFields;
  content: ContentFields;
  user_context?: string | null;
  media?: MediaReference | null;
  entities: EntityFields;
  semantics: SemanticFields;
  temporal: TemporalFields;
  additional_attributes: AdditionalAttribute[];
  processing: ProcessingFields;
}

export interface MemoryItem {
  id: string;
  title: string;
  type: MemoryType;
  timestamp: string;
  dateStr: string;
  location?: string;
  snippet: string;
  fullContent?: string;
  transcript?: string;
  audioUri?: string;
  imageUri?: string;
  mediaUrl?: string;
  localMediaUri?: string;
  tags: string[];
  sentiment?: 'positive' | 'neutral' | 'reflective' | 'excited';
  privacy: 'private' | 'group' | 'encrypted';
  isEncrypted?: boolean;
  timeOfDay?: string;
  created_at?: string;
  groupName?: string;
  entities?: { name: string; type: 'person' | 'place' | 'concept' | 'date' | 'amount' }[];
  rawMemoryV1?: MemoryV1;
}

export interface TextIngestionPayload {
  text: string;
  privacy?: Privacy;
  group_id?: string | null;
}

export interface ImageIngestionPayload {
  uri: string;
  name?: string;
  type?: string;
  context?: string;
  privacy?: Privacy;
  group_id?: string | null;
}

export interface AudioIngestionPayload {
  uri: string;
  name?: string;
  type?: string;
  context?: string;
  privacy?: Privacy;
  group_id?: string | null;
}

export interface MemorySearchRequest {
  query: string;
  top_k?: number;
  content_weight?: number;
  context_weight?: number;
  generate_answer?: boolean;
}

export interface SearchResultItem {
  memory_id: string;
  score: number;
  similarity_score?: number;
  source_modality?: string;
  user_context?: string | null;
  clean_text?: string | null;
  media?: MediaReference | null;
  content_score?: number | null;
  context_score?: number | null;
  summary?: string | null;
  entities?: Record<string, any> | null;
  semantics?: Record<string, any> | null;
  memory: MemoryV1;
}

export interface MemorySearchResponse {
  query: string;
  answer?: string | null;
  grounded?: boolean;
  results: SearchResultItem[];
  total_results: number;
}

export interface RawFeedItem {
  id: string;
  media_type: 'text' | 'image' | 'audio' | string;
  raw_payload: string;
  structured_payload?: Record<string, any> | null;
  received_at: string;
  status: string;
  user_context?: string | null;
  original_filename?: string | null;
  storage_key?: string | null;
  media_url?: string | null;
  group_id?: string | null;
}

export interface FeedResponse {
  total_count: number;
  items: RawFeedItem[];
}

export type GroupRole = 'OWNER' | 'ADMIN' | 'CONTRIBUTOR' | 'MEMBER' | 'GUEST';

export interface Group {
  id: string;
  name: string;
  description?: string | null;
  creator_id: string;
  is_archived: boolean;
  member_count?: number;
  my_role?: GroupRole;
  created_at: string;
  updated_at?: string;
}

export interface GroupMember {
  id: string;
  group_id: string;
  user_id: string;
  username: string;
  role: GroupRole;
  joined_at: string;
}

export interface GroupInvitation {
  id: string;
  group_id: string;
  group_name?: string;
  inviter_id: string;
  invitee_email: string;
  role: GroupRole;
  status: 'pending' | 'accepted' | 'rejected' | 'revoked' | 'expired';
  invitation_token?: string;
  expires_at: string;
  created_at: string;
}

export interface CommentItem {
  id: string;
  memory_id: string;
  author_id: string;
  author_username: string;
  content: string;
  is_knowledge_eligible: boolean;
  derived_memory_id?: string | null;
  created_at: string;
  updated_at?: string;
}

export interface GroupShare {
  id: string;
  group_id: string;
  granted_by: string;
  created_at: string;
}

export interface UserShare {
  id: string;
  user_id: string;
  permissions: string[];
  granted_by: string;
  created_at: string;
}

export interface MemorySharesResponse {
  memory_id: string;
  group_shares: GroupShare[];
  user_shares: UserShare[];
}

export interface UserSearchResult {
  id: string;
  username: string;
}


