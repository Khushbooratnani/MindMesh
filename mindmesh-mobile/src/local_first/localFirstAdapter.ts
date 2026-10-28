/**
 * Local-First Private Locker Adapter.
 * Bridges mobile UI with:
 * 1. Isolated authentication database API (/api/v2/locker-auth)
 * 2. Device Key Manager (DEK generation and wrapping)
 * 3. Local Encrypted Storage (AES-256-GCM local storage and local vector search)
 * 4. Consented Ephemeral AI processing (/api/v2/ephemeral-ai)
 */

import { getApiUrl } from '../config/apiConfig';
import { authService } from '../auth/authService';
import {
  DecryptedLocalMemory,
  EphemeralAiConsent,
  LocalFirstLockerStatus,
  LocalSearchResult,
  EncryptedBackupArchive,
} from './types';
import { deviceKeyManager } from './deviceKeyManager';
import { localEncryptedStorage } from './localEncryptedStorage';

export class LocalFirstAdapter {
  /**
   * Fetches the local-first locker status from the isolated auth database.
   */
  async checkStatus(): Promise<LocalFirstLockerStatus> {
    const headers = await authService.getLockerHeaders();
    const res = await fetch(getApiUrl('/api/v2/locker-auth/status'), {
      method: 'GET',
      headers,
    });
    if (!res.ok) {
      if (res.status === 404) {
        return { has_locker: false, exists: false, locked_out: false, status: 'locked' };
      }
      throw new Error(`Failed to check local locker status: ${res.statusText}`);
    }
    const data = await res.json();
    return {
      has_locker: data.has_locker,
      exists: data.exists,
      locked_out: data.locked_out,
      status: deviceKeyManager.isUnlocked() ? 'unlocked' : 'locked',
    };
  }

  /**
   * Registers a new local-first locker on the separate auth database and initializes local DEK.
   */
  async createLocker(password: string): Promise<{ recoveryKey: string }> {
    const headers = await authService.getLockerHeaders();
    // 1. Initialize local key envelope
    await deviceKeyManager.initializeNewLockerKey(password);

    // 2. Register verifier in isolated auth database
    const res = await fetch(getApiUrl('/api/v2/locker-auth/register'), {
      method: 'POST',
      headers,
      body: JSON.stringify({ password }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'Locker registration failed on auth server.');
    }

    const data = await res.json();
    return { recoveryKey: data.recovery_key };
  }

  /**
   * Unlocks both the server authentication session and the local encryption key.
   */
  async unlock(password: string): Promise<{ token: string; expires_in_seconds: number }> {
    const headers = await authService.getLockerHeaders();
    const res = await fetch(getApiUrl('/api/v2/locker-auth/unlock'), {
      method: 'POST',
      headers,
      body: JSON.stringify({ password }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'Failed to unlock locker.');
    }

    const data = await res.json();

    // If local key is not yet initialized or locked, initialize/unlock local envelope
    if (!deviceKeyManager.isUnlocked()) {
      await deviceKeyManager.initializeNewLockerKey(password);
    }

    return data;
  }

  /**
   * Locks the locker on both the server and locally zeroizes memory keys.
   */
  async lock(): Promise<void> {
    try {
      const headers = await authService.getLockerHeaders();
      await fetch(getApiUrl('/api/v2/locker-auth/lock'), {
        method: 'POST',
        headers,
      });
    } catch (e) {
      console.warn('Server lock notification failed, locking local store anyway:', e);
    } finally {
      deviceKeyManager.lockLocker();
    }
  }

  /**
   * Saves a private memory locally.
   * If consent is granted, runs temporary server-side semantic extraction without persistence.
   */
  async savePrivateMemory(params: {
    id: string;
    text: string;
    title?: string;
    mediaUri?: string;
    mediaType?: 'text' | 'image' | 'audio';
    consent?: EphemeralAiConsent;
  }): Promise<DecryptedLocalMemory> {
    if (!deviceKeyManager.isUnlocked()) {
      throw new Error('Locker is locked. Unlock to save private memories.');
    }

    let entities: Record<string, any> = {};
    let semantics: Record<string, any> = {};
    let embedding: number[] | undefined;

    // Optional ephemeral AI processing with verified consent
    if (params.consent && params.consent.consent_granted) {
      const headers = await authService.getLockerHeaders();
      try {
        // Ephemeral Phase 1 extraction
        const extRes = await fetch(getApiUrl('/api/v2/ephemeral-ai/extract'), {
          method: 'POST',
          headers,
          body: JSON.stringify({
            consent: params.consent,
            text: params.text,
          }),
        });
        if (extRes.ok) {
          const extData = await extRes.json();
          entities = extData.entities || {};
          semantics = extData.semantics || {};
        }

        // Ephemeral BGE-M3 embedding for local search
        const embedRes = await fetch(getApiUrl('/api/v2/ephemeral-ai/embed'), {
          method: 'POST',
          headers,
          body: JSON.stringify({
            consent: { ...params.consent, purpose: 'embedding_generation' },
            texts: [params.text],
          }),
        });
        if (embedRes.ok) {
          const embedData = await embedRes.json();
          if (embedData.embeddings && embedData.embeddings.length > 0) {
            embedding = embedData.embeddings[0];
          }
        }
      } catch (aiErr) {
        console.warn('Ephemeral AI processing skipped or failed, saving memory locally:', aiErr);
      }
    }

    await localEncryptedStorage.saveMemory({
      id: params.id,
      text: params.text,
      title: params.title,
      entities,
      semantics,
      localEmbedding: embedding,
      mediaUri: params.mediaUri,
    });

    const saved = await localEncryptedStorage.getMemory(params.id);
    if (!saved) throw new Error('Failed to retrieve freshly written local memory');
    return saved;
  }

  /**
   * Retrieves all local private memories.
   */
  async listPrivateMemories(): Promise<DecryptedLocalMemory[]> {
    return await localEncryptedStorage.listMemories();
  }

  /**
   * Searches local private memories using local vector similarity or textual fallback.
   */
  async searchPrivateMemories(query: string, consent?: EphemeralAiConsent): Promise<LocalSearchResult[]> {
    if (!deviceKeyManager.isUnlocked()) {
      throw new Error('Locker is locked. Unlock to search private memories.');
    }

    let queryVector: number[] | null = null;
    if (consent && consent.consent_granted) {
      try {
        const headers = await authService.getLockerHeaders();
        const res = await fetch(getApiUrl('/api/v2/ephemeral-ai/embed'), {
          method: 'POST',
          headers,
          body: JSON.stringify({
            consent,
            texts: [query],
          }),
        });
        if (res.ok) {
          const data = await res.json();
          queryVector = data.embeddings[0];
        }
      } catch (e) {
        console.warn('Ephemeral query embedding failed, falling back to local text matching:', e);
      }
    }

    if (queryVector) {
      return await localEncryptedStorage.searchMemories(queryVector);
    }

    // Textual fallback matching if embedding unavailable
    const all = await localEncryptedStorage.listMemories();
    const lowered = query.toLowerCase();
    const matched = all
      .filter(m => m.text.toLowerCase().includes(lowered) || m.title.toLowerCase().includes(lowered))
      .map(m => ({ memory: m, similarityScore: 1.0 }));
    return matched;
  }

  /**
   * Deletes a local memory.
   */
  async deletePrivateMemory(id: string): Promise<boolean> {
    return await localEncryptedStorage.deleteMemory(id);
  }

  /**
   * Exports an encrypted backup of all local private memories.
   */
  async exportBackup(backupPassphrase: string): Promise<EncryptedBackupArchive> {
    const records = localEncryptedStorage.getAllEncryptedRecords();
    const serialized = JSON.stringify(records);
    return await deviceKeyManager.exportEncryptedBackup(serialized, backupPassphrase);
  }

  /**
   * Imports and restores memories from an encrypted backup archive.
   */
  async importBackup(backup: EncryptedBackupArchive, backupPassphrase: string): Promise<number> {
    const decryptedJson = await deviceKeyManager.restoreEncryptedBackup(backup, backupPassphrase);
    const records = JSON.parse(decryptedJson);
    if (!Array.isArray(records)) {
      throw new Error('Malformed backup archive payload.');
    }
    localEncryptedStorage.importEncryptedRecords(records);
    return records.length;
  }
}

export const localFirstAdapter = new LocalFirstAdapter();
