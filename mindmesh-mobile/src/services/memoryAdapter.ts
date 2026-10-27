import { MemoryItem, MemoryType, MemoryV1, RawFeedItem } from '../types';
import { getApiUrl } from '../config/apiConfig';

export function convertMemoryV1ToMemoryItem(
  memoryV1: MemoryV1,
  mediaUri?: string
): MemoryItem {
  const typeMap: Record<string, MemoryType> = {
    text: 'note',
    image: 'photo',
    audio: 'voice',
  };

  const type: MemoryType = typeMap[memoryV1.system.media_type] || 'note';

  let dateStr = 'Just now';
  try {
    const d = new Date(memoryV1.system.created_at);
    if (!isNaN(d.getTime())) {
      dateStr = d.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    }
  } catch {
    dateStr = 'Today';
  }

  const entities: { name: string; type: 'person' | 'place' | 'concept' | 'date' | 'amount' }[] = [];

  memoryV1.entities?.people?.forEach((p) => {
    entities.push({ name: p, type: 'person' });
  });

  const places = [
    ...(memoryV1.entities?.places || []),
    ...(memoryV1.entities?.locations || []),
  ];
  Array.from(new Set(places)).forEach((loc) => {
    entities.push({ name: loc, type: 'place' });
  });

  memoryV1.entities?.events?.forEach((e) => {
    entities.push({ name: e, type: 'concept' });
  });

  memoryV1.entities?.organizations?.forEach((org) => {
    entities.push({ name: org, type: 'concept' });
  });

  memoryV1.temporal?.mentioned_dates?.forEach((date) => {
    entities.push({ name: date, type: 'date' });
  });

  const tags = Array.from(
    new Set([
      ...(memoryV1.semantics?.topics || []),
      ...(memoryV1.semantics?.activities || []),
      ...(memoryV1.semantics?.mood || []),
    ])
  );

  const location = places.length > 0 ? places.join(', ') : undefined;

  const title = memoryV1.content?.summary
    ? memoryV1.content.summary.length > 55
      ? memoryV1.content.summary.slice(0, 52) + '...'
      : memoryV1.content.summary
    : memoryV1.content?.description
    ? memoryV1.content.description.slice(0, 48) + '...'
    : 'MindMesh Memory';

  const sentimentMap: Record<string, 'positive' | 'neutral' | 'reflective' | 'excited'> = {
    positive: 'positive',
    neutral: 'neutral',
    negative: 'reflective',
    mixed: 'reflective',
    unknown: 'neutral',
  };

  return {
    id: memoryV1.memory_id,
    title,
    type,
    timestamp: 'Just now',
    dateStr,
    location,
    snippet: memoryV1.content?.summary || memoryV1.content?.description || memoryV1.content?.clean_text || '',
    fullContent: memoryV1.content?.description || memoryV1.content?.clean_text || '',
    transcript: memoryV1.system.media_type === 'audio' ? memoryV1.content?.raw_text || memoryV1.content?.clean_text : undefined,
    imageUri: memoryV1.system.media_type === 'image' ? mediaUri : undefined,
    audioUri: memoryV1.system.media_type === 'audio' ? mediaUri : undefined,
    tags: tags.length > 0 ? tags : ['Memory', memoryV1.system.media_type],
    sentiment: sentimentMap[memoryV1.semantics?.sentiment] || 'neutral',
    privacy: memoryV1.system.privacy === 'ONLY_ME' ? 'private' : memoryV1.system.privacy === 'GROUP' ? 'group' : 'encrypted',
    groupName: memoryV1.system.group_id || undefined,
    entities,
    rawMemoryV1: memoryV1,
  };
}

export function convertSearchResultToMemoryItem(
  resultItem: { memory_id?: string; score?: number; memory?: MemoryV1 }
): MemoryItem {
  if (resultItem.memory) {
    // Resolve any media URI if available
    let mediaUri: string | undefined;
    const mediaObj = (resultItem.memory as any).media;
    const storageKey =
      mediaObj?.storage_key ||
      (resultItem.memory.system as any)?.media_reference ||
      mediaObj?.relative_path;

    if (mediaObj?.url) {
      mediaUri = mediaObj.url.startsWith('http')
        ? mediaObj.url
        : getApiUrl(mediaObj.url);
    } else if (storageKey) {
      mediaUri = getApiUrl(`/api/v1/media/${storageKey}`);
    }

    return convertMemoryV1ToMemoryItem(resultItem.memory, mediaUri);
  }

  // Fallback if raw result structure
  return {
    id: resultItem.memory_id || 'mem-unknown',
    title: 'Search Result',
    type: 'note',
    timestamp: 'Just now',
    dateStr: 'Retrieved',
    snippet: '',
    fullContent: '',
    tags: ['Retrieved'],
    sentiment: 'neutral',
    privacy: 'private',
    entities: [],
  };
}

export function convertRawFeedItemToMemoryItem(item: RawFeedItem): MemoryItem {
  const typeMap: Record<string, MemoryType> = {
    text: 'note',
    image: 'photo',
    audio: 'voice',
  };

  const type: MemoryType = typeMap[item.media_type] || 'note';

  let dateStr = 'Just now';
  try {
    const d = new Date(item.received_at);
    if (!isNaN(d.getTime())) {
      dateStr = d.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    }
  } catch {
    dateStr = 'Today';
  }

  const st = item.structured_payload || {};
  const storageKey = item.storage_key || st.storage_key || st.relative_path;
  const mediaUri = item.media_url || (storageKey ? getApiUrl(`/api/v1/media/${storageKey}`) : undefined);

  let title = 'Raw Memory';
  let snippet = item.raw_payload;

  if (item.media_type === 'text') {
    title = item.raw_payload.length > 55 ? item.raw_payload.slice(0, 52) + '...' : item.raw_payload;
    snippet = item.raw_payload;
  } else if (item.media_type === 'image') {
    const context = item.user_context || st.user_context;
    title = context ? (context.length > 55 ? context.slice(0, 52) + '...' : context) : (item.original_filename || st.original_filename || 'Photo Memory');
    snippet = context || item.raw_payload || 'Photo memory';
  } else if (item.media_type === 'audio') {
    const context = item.user_context || st.user_context;
    title = context ? (context.length > 55 ? context.slice(0, 52) + '...' : context) : (item.original_filename || st.original_filename || 'Voice Memo');
    snippet = context || item.raw_payload || 'Voice memo';
  }

  return {
    id: item.id,
    title,
    type,
    timestamp: 'Just now',
    dateStr,
    snippet,
    fullContent: item.raw_payload,
    imageUri: item.media_type === 'image' ? mediaUri : undefined,
    audioUri: item.media_type === 'audio' ? mediaUri : undefined,
    tags: [item.media_type.toUpperCase(), item.status],
    sentiment: 'neutral',
    privacy: 'private',
    groupName: item.group_id || undefined,
    entities: [],
  };
}
