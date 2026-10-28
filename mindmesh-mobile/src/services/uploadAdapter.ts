import { Platform } from 'react-native';
import * as FileSystem from 'expo-file-system/legacy';
import { authStorage } from '../auth/authStorage';
import { MemoryV1 } from '../types';

export interface UploadFileOptions {
  url: string;
  uri: string;
  filename: string;
  mimeType: string;
  parameters: Record<string, string>;
  timeoutMs?: number;
}

/**
 * Builds standard authentication and private locker headers.
 */
async function buildUploadHeaders(): Promise<Record<string, string>> {
  const headers: Record<string, string> = {
    Accept: 'application/json',
  };

  const session = await authStorage.getSession();
  if (session?.token) {
    headers['Authorization'] = `Bearer ${session.token}`;
  }

  const lockerToken = await authStorage.getLockerToken();
  if (lockerToken) {
    headers['X-Locker-Token'] = lockerToken;
  }

  return headers;
}

/**
 * Parses server response or fallback error message.
 */
function parseServerResponse(statusCode: number, responseBody: string): MemoryV1 {
  let parsed: any = null;
  try {
    parsed = JSON.parse(responseBody);
  } catch {
    // Non-JSON response
  }

  if (statusCode >= 200 && statusCode < 300) {
    if (parsed) {
      return parsed as MemoryV1;
    }
    throw new Error(`Upload succeeded with status ${statusCode} but returned non-JSON payload.`);
  }

  let message: string;
  if (Array.isArray(parsed?.detail) && parsed.detail.length > 0) {
    const fieldErrors = parsed.detail.map((d: any) => {
      const field = Array.isArray(d.loc) ? d.loc[d.loc.length - 1] : '';
      const msg = d.msg || 'Invalid field';
      return field ? `${field}: ${msg}` : msg;
    });
    message = `Validation Error: ${fieldErrors.join('; ')}`;
  } else if (typeof parsed?.detail === 'string') {
    message = parsed.detail;
  } else if (parsed?.error?.message) {
    message = parsed.error.message;
  } else if (parsed?.message) {
    message = parsed.message;
  } else {
    message = `Upload failed with HTTP ${statusCode}`;
  }

  throw new Error(message);
}

/**
 * Universal upload adapter compatible with Expo SDK 57 and React Native 0.86+.
 * 
 * On Native (iOS & Android):
 * Uses FileSystem.uploadAsync with FileSystemUploadType.MULTIPART, streaming
 * directly from disk via native NSURLSession / OkHttp. This completely avoids
 * the "Unsupported FormDataPart implementation" error thrown by modern React Native fetch.
 * 
 * On Web:
 * Fetches the local resource as a standard Blob and appends it to native FormData.
 */
export async function uploadFileMultipart(options: UploadFileOptions): Promise<MemoryV1> {
  const { url, uri, filename, mimeType, parameters } = options;
  const headers = await buildUploadHeaders();

  if (Platform.OS !== 'web') {
    // -------------------------------------------------------------
    // NATIVE (iOS / Android) — Expo FileSystem uploadAsync
    // -------------------------------------------------------------
    try {
      let cleanUri = uri;
      if (Platform.OS === 'android' && !cleanUri.startsWith('file://') && !cleanUri.startsWith('content://')) {
        cleanUri = `file://${cleanUri}`;
      }

      const result = await FileSystem.uploadAsync(url, cleanUri, {
        httpMethod: 'POST',
        uploadType: FileSystem.FileSystemUploadType.MULTIPART,
        fieldName: 'file',
        mimeType: mimeType || (cleanUri.endsWith('.m4a') ? 'audio/m4a' : 'image/jpeg'),
        parameters,
        headers,
      });

      return parseServerResponse(result.status, result.body);
    } catch (err: any) {
      console.error('[UploadAdapter Native Error]', err);
      throw new Error(err.message || 'Failed to upload media on native device.');
    }
  }

  // -------------------------------------------------------------
  // WEB PLATFORM — Standard W3C FormData with Blob
  // -------------------------------------------------------------
  try {
    const formData = new FormData();

    // Convert web URI to standard Blob
    const response = await fetch(uri);
    const blob = await response.blob();
    formData.append('file', blob, filename);

    // Append form parameters
    for (const [key, val] of Object.entries(parameters)) {
      formData.append(key, val);
    }

    const res = await fetch(url, {
      method: 'POST',
      headers,
      body: formData,
    });

    const responseText = await res.text();
    return parseServerResponse(res.status, responseText);
  } catch (err: any) {
    console.error('[UploadAdapter Web Error]', err);
    throw new Error(err.message || 'Failed to upload media on web.');
  }
}
