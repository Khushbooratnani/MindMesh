import { Platform } from 'react-native';
import { getApiUrl } from '../config/apiConfig';
import { authStorage } from '../auth/authStorage';
import {
  MemoryV1,
  TextIngestionPayload,
  ImageIngestionPayload,
  AudioIngestionPayload,
  Group,
  GroupMember,
  GroupInvitation,
  CommentItem,
  MemorySharesResponse,
  UserSearchResult,
  GroupRole,
} from '../types';

async function getAuthHeaders(
  baseHeaders: Record<string, string> = {},
  includeLockerToken = false
): Promise<Record<string, string>> {
  const headers = { ...baseHeaders };
  const session = await authStorage.getSession();
  if (session?.token) {
    headers['Authorization'] = `Bearer ${session.token}`;
  }
  if (includeLockerToken) {
    const lockerToken = await authStorage.getLockerToken();
    if (lockerToken) {
      headers['X-Locker-Token'] = lockerToken;
    }
  }
  return headers;
}

import { toBackendPrivacy } from './privacyMapper';

async function parseError(response: Response): Promise<string> {
  try {
    const data = await response.json();
    if (data?.error?.message) {
      return data.error.message;
    }
    if (Array.isArray(data?.detail) && data.detail.length > 0) {
      const fieldErrors = data.detail.map((d: any) => {
        const field = Array.isArray(d.loc) ? d.loc[d.loc.length - 1] : '';
        const msg = d.msg || 'Invalid field';
        return field ? `${field}: ${msg}` : msg;
      });
      return `Validation Error: ${fieldErrors.join('; ')}`;
    }
    if (typeof data?.detail === 'string') {
      return data.detail;
    }
    if (data?.message) {
      return data.message;
    }
  } catch {
    // ignore json parsing errors
  }
  return `Server request failed (${response.status}: ${response.statusText})`;
}

async function appendFileToFormData(
  formData: FormData,
  fieldName: string,
  uri: string,
  filename: string,
  mimeType: string
): Promise<void> {
  if (Platform.OS === 'web') {
    try {
      const res = await fetch(uri);
      const blob = await res.blob();
      formData.append(fieldName, blob, filename);
      return;
    } catch {
      // Fallback if fetch blob fails on web
      formData.append(fieldName, { uri, name: filename, type: mimeType } as any, filename);
      return;
    }
  }

  // Native iOS / Android React Native standard FormData polyfill format
  let cleanUri = uri;
  if (Platform.OS === 'android' && !cleanUri.startsWith('file://') && !cleanUri.startsWith('content://')) {
    cleanUri = `file://${cleanUri}`;
  }

  formData.append(fieldName, {
    uri: cleanUri,
    name: filename,
    type: mimeType,
  } as any);
}

import { uploadFileMultipart } from './uploadAdapter';

export async function ingestTextMemory(payload: TextIngestionPayload, timeoutMs = 35000): Promise<MemoryV1> {
  const url = getApiUrl('/api/v1/memories/ingest');

  const body = {
    text: payload.text,
    media_type: 'text',
    privacy: toBackendPrivacy(payload.privacy),
    group_id: payload.group_id || null,
    allowed_users: [],
  };

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: await getAuthHeaders({
        'Content-Type': 'application/json',
        Accept: 'application/json',
      }),
      body: JSON.stringify(body),
      signal: controller.signal,
    });

    if (!response.ok) {
      const errorMsg = await parseError(response);
      throw new Error(errorMsg);
    }

    return (await response.json()) as MemoryV1;
  } catch (err: any) {
    if (err.name === 'AbortError') {
      throw new Error('Memory ingestion timed out after 35s. Please check server connection.');
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

export async function ingestImageMemory(payload: ImageIngestionPayload): Promise<MemoryV1> {
  const url = getApiUrl('/api/v1/memories/ingest/image');
  const filename = payload.name || 'photo.jpg';
  const fileType = payload.type || 'image/jpeg';

  const parameters: Record<string, string> = {
    media_type: 'image',
    privacy: toBackendPrivacy(payload.privacy),
    allowed_users: '[]',
  };

  if (payload.context && payload.context.trim()) {
    parameters.context = payload.context.trim();
  }
  if (payload.group_id) {
    parameters.group_id = payload.group_id;
  }

  return await uploadFileMultipart({
    url,
    uri: payload.uri,
    filename,
    mimeType: fileType,
    parameters,
  });
}

export async function ingestAudioMemory(payload: AudioIngestionPayload): Promise<MemoryV1> {
  const url = getApiUrl('/api/v1/memories/ingest/audio');
  const filename = payload.name || 'recording.m4a';
  const fileType = payload.type || 'audio/m4a';

  const parameters: Record<string, string> = {
    media_type: 'audio',
    privacy: toBackendPrivacy(payload.privacy),
    allowed_users: '[]',
  };

  if (payload.context && payload.context.trim()) {
    parameters.context = payload.context.trim();
  }
  if (payload.group_id) {
    parameters.group_id = payload.group_id;
  }

  return await uploadFileMultipart({
    url,
    uri: payload.uri,
    filename,
    mimeType: fileType,
    parameters,
  });
}

export async function searchMemories(payload: {
  query: string;
  top_k?: number;
  content_weight?: number;
  context_weight?: number;
  generate_answer?: boolean;
  group_id?: string | null;
}): Promise<{
  query: string;
  answer?: string;
  grounded?: boolean;
  results: any[];
  total_results?: number;
}> {
  const url = getApiUrl('/api/v1/memories/search');

  const body: Record<string, any> = {
    query: payload.query.trim(),
    top_k: payload.top_k ?? 5,
    content_weight: payload.content_weight ?? 0.5,
    context_weight: payload.context_weight ?? 0.5,
    generate_answer: payload.generate_answer ?? true,
  };
  if (payload.group_id) {
    body.group_id = payload.group_id;
  }

  const response = await fetch(url, {
    method: 'POST',
    headers: await getAuthHeaders({
      'Content-Type': 'application/json',
      Accept: 'application/json',
    }),
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const errorMsg = await parseError(response);
    throw new Error(errorMsg);
  }

  return await response.json();
}

export async function getRawFeed(
  limit: number = 150,
  offset: number = 0,
  groupId?: string | null
): Promise<{
  total_count: number;
  items: any[];
}> {
  let endpoint = `/api/v1/memories/feed?limit=${limit}&offset=${offset}`;
  if (groupId) {
    endpoint += `&group_id=${encodeURIComponent(groupId)}`;
  }
  const url = getApiUrl(endpoint);

  const response = await fetch(url, {
    method: 'GET',
    headers: await getAuthHeaders({
      Accept: 'application/json',
    }),
  });

  if (!response.ok) {
    const errorMsg = await parseError(response);
    throw new Error(errorMsg);
  }

  return await response.json();
}

export async function getLockerMemories(
  limit: number = 100,
  offset: number = 0
): Promise<{
  total_count: number;
  items: any[];
}> {
  const url = getApiUrl(`/api/v1/locker/memories?limit=${limit}&offset=${offset}`);

  const response = await fetch(url, {
    method: 'GET',
    headers: await getAuthHeaders(
      {
        Accept: 'application/json',
      },
      true // includeLockerToken
    ),
  });

  if (!response.ok) {
    const errorMsg = await parseError(response);
    throw new Error(errorMsg);
  }

  return await response.json();
}

export async function recoverLockerPassword(
  recoveryKey: string,
  newPassword: string
): Promise<{ message: string; new_recovery_key: string }> {
  const url = getApiUrl('/api/v1/locker/recover');

  const response = await fetch(url, {
    method: 'POST',
    headers: await getAuthHeaders({
      'Content-Type': 'application/json',
      Accept: 'application/json',
    }),
    body: JSON.stringify({
      recovery_key: recoveryKey,
      new_password: newPassword,
    }),
  });

  if (!response.ok) {
    const errorMsg = await parseError(response);
    throw new Error(errorMsg);
  }

  return await response.json();
}

export async function changeLockerPassword(
  oldPassword: string,
  newPassword: string
): Promise<{ message: string }> {
  const url = getApiUrl('/api/v1/locker/change-password');

  const response = await fetch(url, {
    method: 'POST',
    headers: await getAuthHeaders({
      'Content-Type': 'application/json',
      Accept: 'application/json',
    }),
    body: JSON.stringify({
      old_password: oldPassword,
      new_password: newPassword,
    }),
  });

  if (!response.ok) {
    const errorMsg = await parseError(response);
    throw new Error(errorMsg);
  }

  return await response.json();
}

// -------------------------------------------------------------
// GROUPS & ACL API CLIENT METHODS
// -------------------------------------------------------------

// Optional feature gate detection for groups
let isGroupsSupported: boolean | null = null;

export async function getGroups(): Promise<Group[]> {
  if (isGroupsSupported === false) {
    return [];
  }
  const url = getApiUrl('/api/v1/groups');
  try {
    const response = await fetch(url, {
      method: 'GET',
      headers: await getAuthHeaders({ Accept: 'application/json' }),
    });
    if (!response.ok) {
      if (response.status === 404) {
        // Groups API not mounted on this server; cache and isolate gracefully without throwing
        isGroupsSupported = false;
        return [];
      }
      const errorMsg = await parseError(response);
      throw new Error(errorMsg);
    }
    isGroupsSupported = true;
    return await response.json();
  } catch (err: any) {
    if (isGroupsSupported === false) return [];
    throw err;
  }
}

export async function createGroup(name: string, description?: string): Promise<Group> {
  const url = getApiUrl('/api/v1/groups');
  const response = await fetch(url, {
    method: 'POST',
    headers: await getAuthHeaders({
      'Content-Type': 'application/json',
      Accept: 'application/json',
    }),
    body: JSON.stringify({ name: name.trim(), description: description?.trim() || null }),
  });
  if (!response.ok) {
    const errorMsg = await parseError(response);
    throw new Error(errorMsg);
  }
  return await response.json();
}

export async function getGroupDetails(groupId: string): Promise<Group> {
  const url = getApiUrl(`/api/v1/groups/${encodeURIComponent(groupId)}`);
  const response = await fetch(url, {
    method: 'GET',
    headers: await getAuthHeaders({ Accept: 'application/json' }),
  });
  if (!response.ok) {
    const errorMsg = await parseError(response);
    throw new Error(errorMsg);
  }
  return await response.json();
}

export async function updateGroup(
  groupId: string,
  name?: string,
  description?: string,
  isArchived?: boolean
): Promise<Group> {
  const url = getApiUrl(`/api/v1/groups/${encodeURIComponent(groupId)}`);
  const body: Record<string, any> = {};
  if (name !== undefined) body.name = name;
  if (description !== undefined) body.description = description;
  if (isArchived !== undefined) body.is_archived = isArchived;

  const response = await fetch(url, {
    method: 'PATCH',
    headers: await getAuthHeaders({
      'Content-Type': 'application/json',
      Accept: 'application/json',
    }),
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const errorMsg = await parseError(response);
    throw new Error(errorMsg);
  }
  return await response.json();
}

export async function deleteGroup(groupId: string): Promise<{ message: string }> {
  const url = getApiUrl(`/api/v1/groups/${encodeURIComponent(groupId)}`);
  const response = await fetch(url, {
    method: 'DELETE',
    headers: await getAuthHeaders({ Accept: 'application/json' }),
  });
  if (!response.ok) {
    const errorMsg = await parseError(response);
    throw new Error(errorMsg);
  }
  return await response.json();
}

export async function transferGroupOwnership(groupId: string, newOwnerId: string): Promise<{ message: string }> {
  const url = getApiUrl(`/api/v1/groups/${encodeURIComponent(groupId)}/transfer-ownership`);
  const response = await fetch(url, {
    method: 'POST',
    headers: await getAuthHeaders({
      'Content-Type': 'application/json',
      Accept: 'application/json',
    }),
    body: JSON.stringify({ new_owner_id: newOwnerId }),
  });
  if (!response.ok) {
    const errorMsg = await parseError(response);
    throw new Error(errorMsg);
  }
  return await response.json();
}

export async function leaveGroup(groupId: string): Promise<{ message: string }> {
  const url = getApiUrl(`/api/v1/groups/${encodeURIComponent(groupId)}/leave`);
  const response = await fetch(url, {
    method: 'POST',
    headers: await getAuthHeaders({ Accept: 'application/json' }),
  });
  if (!response.ok) {
    const errorMsg = await parseError(response);
    throw new Error(errorMsg);
  }
  return await response.json();
}

export async function getGroupMembers(groupId: string): Promise<GroupMember[]> {
  const url = getApiUrl(`/api/v1/groups/${encodeURIComponent(groupId)}/members`);
  const response = await fetch(url, {
    method: 'GET',
    headers: await getAuthHeaders({ Accept: 'application/json' }),
  });
  if (!response.ok) {
    const errorMsg = await parseError(response);
    throw new Error(errorMsg);
  }
  return await response.json();
}

export async function updateMemberRole(
  groupId: string,
  userId: string,
  role: GroupRole
): Promise<GroupMember> {
  const url = getApiUrl(`/api/v1/groups/${encodeURIComponent(groupId)}/members/${encodeURIComponent(userId)}`);
  const response = await fetch(url, {
    method: 'PATCH',
    headers: await getAuthHeaders({
      'Content-Type': 'application/json',
      Accept: 'application/json',
    }),
    body: JSON.stringify({ role }),
  });
  if (!response.ok) {
    const errorMsg = await parseError(response);
    throw new Error(errorMsg);
  }
  return await response.json();
}

export async function removeMember(groupId: string, userId: string): Promise<{ message: string }> {
  const url = getApiUrl(`/api/v1/groups/${encodeURIComponent(groupId)}/members/${encodeURIComponent(userId)}`);
  const response = await fetch(url, {
    method: 'DELETE',
    headers: await getAuthHeaders({ Accept: 'application/json' }),
  });
  if (!response.ok) {
    const errorMsg = await parseError(response);
    throw new Error(errorMsg);
  }
  return await response.json();
}

export async function getGroupInvitations(groupId: string): Promise<GroupInvitation[]> {
  const url = getApiUrl(`/api/v1/groups/${encodeURIComponent(groupId)}/invitations`);
  const response = await fetch(url, {
    method: 'GET',
    headers: await getAuthHeaders({ Accept: 'application/json' }),
  });
  if (!response.ok) {
    const errorMsg = await parseError(response);
    throw new Error(errorMsg);
  }
  return await response.json();
}

export async function createInvitation(
  groupId: string,
  inviteeEmail: string,
  role: GroupRole
): Promise<GroupInvitation> {
  const url = getApiUrl(`/api/v1/groups/${encodeURIComponent(groupId)}/invitations`);
  const response = await fetch(url, {
    method: 'POST',
    headers: await getAuthHeaders({
      'Content-Type': 'application/json',
      Accept: 'application/json',
    }),
    body: JSON.stringify({ invitee_email: inviteeEmail.trim(), role }),
  });
  if (!response.ok) {
    const errorMsg = await parseError(response);
    throw new Error(errorMsg);
  }
  return await response.json();
}

export async function acceptInvitation(token: string): Promise<GroupMember> {
  const url = getApiUrl('/api/v1/groups/invitations/accept');
  const response = await fetch(url, {
    method: 'POST',
    headers: await getAuthHeaders({
      'Content-Type': 'application/json',
      Accept: 'application/json',
    }),
    body: JSON.stringify({ token: token.trim() }),
  });
  if (!response.ok) {
    const errorMsg = await parseError(response);
    throw new Error(errorMsg);
  }
  return await response.json();
}

export async function rejectInvitation(token: string): Promise<{ message: string }> {
  const url = getApiUrl('/api/v1/groups/invitations/reject');
  const response = await fetch(url, {
    method: 'POST',
    headers: await getAuthHeaders({
      'Content-Type': 'application/json',
      Accept: 'application/json',
    }),
    body: JSON.stringify({ token: token.trim() }),
  });
  if (!response.ok) {
    const errorMsg = await parseError(response);
    throw new Error(errorMsg);
  }
  return await response.json();
}

export async function revokeInvitation(invitationId: string): Promise<{ message: string }> {
  const url = getApiUrl(`/api/v1/groups/invitations/${encodeURIComponent(invitationId)}/revoke`);
  const response = await fetch(url, {
    method: 'POST',
    headers: await getAuthHeaders({ Accept: 'application/json' }),
  });
  if (!response.ok) {
    const errorMsg = await parseError(response);
    throw new Error(errorMsg);
  }
  return await response.json();
}

export async function searchUsers(query: string): Promise<UserSearchResult[]> {
  const url = getApiUrl(`/api/v1/groups/users/search?q=${encodeURIComponent(query.trim())}`);
  const response = await fetch(url, {
    method: 'GET',
    headers: await getAuthHeaders({ Accept: 'application/json' }),
  });
  if (!response.ok) {
    const errorMsg = await parseError(response);
    throw new Error(errorMsg);
  }
  return await response.json();
}

// -------------------------------------------------------------
// RESOURCE-LEVEL SHARING API CLIENT METHODS
// -------------------------------------------------------------

export async function getMemoryShares(memoryId: string): Promise<MemorySharesResponse> {
  const url = getApiUrl(`/api/v1/memories/${encodeURIComponent(memoryId)}/shares`);
  const response = await fetch(url, {
    method: 'GET',
    headers: await getAuthHeaders({ Accept: 'application/json' }),
  });
  if (!response.ok) {
    const errorMsg = await parseError(response);
    throw new Error(errorMsg);
  }
  return await response.json();
}

export async function shareMemory(
  memoryId: string,
  groupIds?: string[],
  userShares?: { user_id: string; permissions?: string[] }[]
): Promise<{ message: string }> {
  const url = getApiUrl(`/api/v1/memories/${encodeURIComponent(memoryId)}/share`);
  const response = await fetch(url, {
    method: 'POST',
    headers: await getAuthHeaders({
      'Content-Type': 'application/json',
      Accept: 'application/json',
    }),
    body: JSON.stringify({
      group_ids: groupIds || [],
      user_shares: userShares || [],
    }),
  });
  if (!response.ok) {
    const errorMsg = await parseError(response);
    throw new Error(errorMsg);
  }
  return await response.json();
}

export async function revokeMemoryShare(
  memoryId: string,
  groupId?: string,
  targetUserId?: string
): Promise<{ message: string }> {
  const url = getApiUrl(`/api/v1/memories/${encodeURIComponent(memoryId)}/revoke`);
  const response = await fetch(url, {
    method: 'POST',
    headers: await getAuthHeaders({
      'Content-Type': 'application/json',
      Accept: 'application/json',
    }),
    body: JSON.stringify({
      group_id: groupId || null,
      target_user_id: targetUserId || null,
    }),
  });
  if (!response.ok) {
    const errorMsg = await parseError(response);
    throw new Error(errorMsg);
  }
  return await response.json();
}

// -------------------------------------------------------------
// COMMENTS API CLIENT METHODS
// -------------------------------------------------------------

export async function getComments(
  memoryId: string,
  limit: number = 50,
  offset: number = 0
): Promise<CommentItem[]> {
  const url = getApiUrl(`/api/v1/memories/${encodeURIComponent(memoryId)}/comments?limit=${limit}&offset=${offset}`);
  const response = await fetch(url, {
    method: 'GET',
    headers: await getAuthHeaders({ Accept: 'application/json' }),
  });
  if (!response.ok) {
    const errorMsg = await parseError(response);
    throw new Error(errorMsg);
  }
  return await response.json();
}

export async function addComment(memoryId: string, content: string): Promise<CommentItem> {
  const url = getApiUrl(`/api/v1/memories/${encodeURIComponent(memoryId)}/comments`);
  const response = await fetch(url, {
    method: 'POST',
    headers: await getAuthHeaders({
      'Content-Type': 'application/json',
      Accept: 'application/json',
    }),
    body: JSON.stringify({ content: content.trim() }),
  });
  if (!response.ok) {
    const errorMsg = await parseError(response);
    throw new Error(errorMsg);
  }
  return await response.json();
}

export async function deleteComment(commentId: string): Promise<{ message: string }> {
  const url = getApiUrl(`/api/v1/memories/comments/${encodeURIComponent(commentId)}`);
  const response = await fetch(url, {
    method: 'DELETE',
    headers: await getAuthHeaders({ Accept: 'application/json' }),
  });
  if (!response.ok) {
    const errorMsg = await parseError(response);
    throw new Error(errorMsg);
  }
  return await response.json();
}

