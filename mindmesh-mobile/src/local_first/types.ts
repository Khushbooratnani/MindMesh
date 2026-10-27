/**
 * Type definitions for MindMesh Local-First Private Locker.
 */

export interface EphemeralAiConsent {
  consent_granted: boolean;
  purpose: 'semantic_extraction' | 'embedding_generation' | 'question_answering';
  retention_policy: 'immediate_destruction';
}

export interface LocalEncryptedMemory {
  id: string;
  version: number;
  encryptedContent: string; // enc:v1:<nonce>:<ciphertext> (AES-GCM)
  encryptedMetadata: string; // enc:v1:<nonce>:<ciphertext> (Entities, tags, sentiment)
  localEmbedding?: number[]; // 1024-dimensional BGE-M3 vector stored locally
  mediaUri?: string; // Path to local encrypted media asset if attached
  checksum: string; // SHA-256 integrity hash
  createdAt: string;
  updatedAt: string;
}

export interface DecryptedLocalMemory {
  id: string;
  text: string;
  title: string;
  entities: Record<string, any>;
  semantics: Record<string, any>;
  mediaUri?: string;
  localEmbedding?: number[];
  createdAt: string;
  updatedAt: string;
}

export interface WrappedKeyEnvelope {
  salt: string; // Base64
  nonce: string; // Base64
  wrappedKey: string; // Base64 ciphertext of DEK
  authTag: string; // Base64 AES-GCM tag
  iterations: number;
}

export interface EncryptedBackupArchive {
  schemaVersion: 'mindmesh-backup-v1';
  exportedAt: string;
  salt: string;
  nonce: string;
  encryptedPayload: string;
  checksum: string;
}

export interface LocalFirstLockerStatus {
  has_locker: boolean;
  exists: boolean;
  locked_out: boolean;
  status: 'locked' | 'unlocked';
}

export interface LocalSearchResult {
  memory: DecryptedLocalMemory;
  similarityScore: number;
}
