import { File as ExpoFile } from 'expo-file-system';
import { getApiUrl } from '../config/apiConfig';
import {
  MemoryV1,
  TextIngestionPayload,
  ImageIngestionPayload,
  AudioIngestionPayload,
} from '../types';

async function parseError(response: Response): Promise<string> {
  try {
    const data = await response.json();
    if (data?.error?.message) {
      return data.error.message;
    }
    if (typeof data?.detail === 'string') {
      return data.detail;
    }
    if (Array.isArray(data?.detail) && data.detail.length > 0) {
      return data.detail.map((d: any) => d.msg || JSON.stringify(d)).join(', ');
    }
    if (data?.message) {
      return data.message;
    }
  } catch {
    // ignore json parsing errors
  }
  return `Server request failed (${response.status}: ${response.statusText})`;
}

function getFileForFormData(uri: string, filename: string, mimeType: string) {
  try {
    const file = new ExpoFile(uri);
    (file as any).type = mimeType;
    return file;
  } catch {
    return {
      name: filename,
      type: mimeType,
      bytes: async () => {
        const res = await fetch(uri);
        const arrayBuf = await res.arrayBuffer();
        return new Uint8Array(arrayBuf);
      },
    };
  }
}

export async function ingestTextMemory(payload: TextIngestionPayload): Promise<MemoryV1> {
  const url = getApiUrl('/api/v1/memories/ingest');

  const body = {
    text: payload.text,
    media_type: 'text',
    privacy: payload.privacy || 'ONLY_ME',
    group_id: payload.group_id || null,
    allowed_users: [],
  };

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const errorMsg = await parseError(response);
    throw new Error(errorMsg);
  }

  return (await response.json()) as MemoryV1;
}

export async function ingestImageMemory(payload: ImageIngestionPayload): Promise<MemoryV1> {
  const url = getApiUrl('/api/v1/memories/ingest/image');
  const formData = new FormData();

  const filename = payload.name || 'photo.jpg';
  const fileType = payload.type || 'image/jpeg';

  const filePart = getFileForFormData(payload.uri, filename, fileType);
  formData.append('file', filePart as any, filename);

  formData.append('media_type', 'image');

  if (payload.context && payload.context.trim()) {
    formData.append('context', payload.context.trim());
  }
  if (payload.group_id) {
    formData.append('group_id', payload.group_id);
  }
  formData.append('privacy', payload.privacy || 'ONLY_ME');
  formData.append('allowed_users', '[]');

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      Accept: 'application/json',
    },
    body: formData,
  });

  if (!response.ok) {
    const errorMsg = await parseError(response);
    throw new Error(errorMsg);
  }

  return (await response.json()) as MemoryV1;
}

export async function ingestAudioMemory(payload: AudioIngestionPayload): Promise<MemoryV1> {
  const url = getApiUrl('/api/v1/memories/ingest/audio');
  const formData = new FormData();

  const filename = payload.name || 'recording.m4a';
  const fileType = payload.type || 'audio/m4a';

  const filePart = getFileForFormData(payload.uri, filename, fileType);
  formData.append('file', filePart as any, filename);

  formData.append('media_type', 'audio');

  if (payload.context && payload.context.trim()) {
    formData.append('context', payload.context.trim());
  }
  if (payload.group_id) {
    formData.append('group_id', payload.group_id);
  }
  formData.append('privacy', payload.privacy || 'ONLY_ME');
  formData.append('allowed_users', '[]');

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      Accept: 'application/json',
    },
    body: formData,
  });

  if (!response.ok) {
    const errorMsg = await parseError(response);
    throw new Error(errorMsg);
  }

  return (await response.json()) as MemoryV1;
}

export async function searchMemories(payload: {
  query: string;
  top_k?: number;
  content_weight?: number;
  context_weight?: number;
  generate_answer?: boolean;
}): Promise<{
  query: string;
  answer?: string;
  grounded?: boolean;
  results: any[];
  total_results?: number;
}> {
  const url = getApiUrl('/api/v1/memories/search');

  const body = {
    query: payload.query.trim(),
    top_k: payload.top_k ?? 5,
    content_weight: payload.content_weight ?? 0.5,
    context_weight: payload.context_weight ?? 0.5,
    generate_answer: payload.generate_answer ?? true,
  };

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
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
  offset: number = 0
): Promise<{
  total_count: number;
  items: any[];
}> {
  const url = getApiUrl(`/api/v1/memories/feed?limit=${limit}&offset=${offset}`);

  const response = await fetch(url, {
    method: 'GET',
    headers: {
      Accept: 'application/json',
    },
  });

  if (!response.ok) {
    const errorMsg = await parseError(response);
    throw new Error(errorMsg);
  }

  return await response.json();
}

