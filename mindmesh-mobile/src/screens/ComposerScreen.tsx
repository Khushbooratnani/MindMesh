import React, { useState, useRef } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  Image,
  StyleSheet,
  Modal,
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import {
  useAudioRecorder,
  RecordingPresets,
  requestRecordingPermissionsAsync,
  setAudioModeAsync,
} from 'expo-audio';
import {
  ingestTextMemory,
  ingestImageMemory,
  ingestAudioMemory,
} from '../services/apiClient';
import { convertMemoryV1ToMemoryItem } from '../services/memoryAdapter';
import { MemoryItem, MemoryV1, ScreenId, Group } from '../types';
import { getGroups } from '../services/apiClient';
import { useAuth } from '../auth/AuthContext';
import { toBackendPrivacy } from '../services/privacyMapper';
import { localFirstAdapter } from '../local_first/localFirstAdapter';
import { localEncryptedStorage } from '../local_first/localEncryptedStorage';
import { deviceKeyManager } from '../local_first/deviceKeyManager';

interface ComposerProps {
  onNavigate: (id: ScreenId) => void;
  onSaveMemory: (newMemory: MemoryItem) => void;
  initialGroupId?: string;
}

interface MediaAttachment {
  type: 'photo' | 'audio';
  uri: string;
  name: string;
  mimeType?: string;
  durationSecs?: number;
}

export const ComposerScreen: React.FC<ComposerProps> = ({
  onNavigate,
  onSaveMemory,
  initialGroupId,
}) => {
  const [inputText, setInputText] = useState('');
  const [attachments, setAttachments] = useState<MediaAttachment[]>([]);
  const [selectedTags, setSelectedTags] = useState<string[]>(['Goa2026', 'Thoughts']);
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [availableGroups, setAvailableGroups] = useState<Group[]>([]);
  const [chosenGroupId, setChosenGroupId] = useState<string | null>(initialGroupId || null);

  // Auth context for locker state
  const { lockerExists, isLockerUnlocked, unlockLocker } = useAuth();
  const [lockerPassword, setLockerPassword] = useState('');
  const [lockerError, setLockerError] = useState<string | null>(null);
  const [isUnlockingLocker, setIsUnlockingLocker] = useState(false);

  // Audio recorder hook via expo-audio
  const audioRecorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const [isRecording, setIsRecording] = useState(false);
  const [recordSecs, setRecordSecs] = useState(0);
  const recordIntervalRef = useRef<any>(null);

  // Processing & Ingestion state
  const [isProcessing, setIsProcessing] = useState(false);
  const [processingStep, setProcessingStep] = useState(1);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Privacy destination modal state
  const [isPrivacyModalOpen, setIsPrivacyModalOpen] = useState(false);
  const [selectedDestination, setSelectedDestination] = useState<'locker' | 'private' | 'group' | 'public'>('private');

  // -------------------------------------------------------------
  // REAL CAMERA & IMAGE GALLERY
  // -------------------------------------------------------------
  const handlePickImage = async () => {
    setIsMenuOpen(false);
    try {
      const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (!permission.granted) {
        Alert.alert('Permission Denied', 'Permission to access photo gallery is required.');
        return;
      }

      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        allowsEditing: true,
        quality: 0.8,
      });

      if (!result.canceled && result.assets && result.assets.length > 0) {
        const asset = result.assets[0];
        setAttachments([
          {
            type: 'photo',
            uri: asset.uri,
            name: asset.fileName || 'photo.jpg',
            mimeType: asset.mimeType || 'image/jpeg',
          },
        ]);
        setErrorMessage(null);
      }
    } catch (err) {
      console.error('Error picking image:', err);
    }
  };

  const handleTakePhoto = async () => {
    setIsMenuOpen(false);
    try {
      const permission = await ImagePicker.requestCameraPermissionsAsync();
      if (!permission.granted) {
        Alert.alert('Permission Denied', 'Permission to access camera is required.');
        return;
      }

      const result = await ImagePicker.launchCameraAsync({
        allowsEditing: true,
        quality: 0.8,
      });

      if (!result.canceled && result.assets && result.assets.length > 0) {
        const asset = result.assets[0];
        setAttachments([
          {
            type: 'photo',
            uri: asset.uri,
            name: asset.fileName || 'camera_snap.jpg',
            mimeType: asset.mimeType || 'image/jpeg',
          },
        ]);
        setErrorMessage(null);
      }
    } catch (err) {
      console.error('Error taking photo:', err);
    }
  };

  // -------------------------------------------------------------
  // REAL AUDIO RECORDING VIA EXPO-AUDIO
  // -------------------------------------------------------------
  const startRecording = async () => {
    try {
      const permission = await requestRecordingPermissionsAsync();
      if (!permission.granted) {
        Alert.alert('Permission Denied', 'Microphone permission is required to record voice memos.');
        return;
      }

      await setAudioModeAsync({
        allowsRecording: true,
        playsInSilentMode: true,
      });

      await audioRecorder.prepareToRecordAsync();
      audioRecorder.record();

      setIsRecording(true);
      setRecordSecs(0);
      setErrorMessage(null);

      recordIntervalRef.current = setInterval(() => {
        setRecordSecs((prev) => prev + 1);
      }, 1000);
    } catch (err: any) {
      console.error('Failed to start recording:', err);
      Alert.alert('Recording Error', err.message || 'Could not start audio recording.');
    }
  };

  const stopRecording = async () => {
    if (recordIntervalRef.current) {
      clearInterval(recordIntervalRef.current);
    }
    setIsRecording(false);

    try {
      await audioRecorder.stop();
      const uri = audioRecorder.uri;

      if (uri) {
        setAttachments([
          {
            type: 'audio',
            uri,
            name: 'voice_memo.m4a',
            mimeType: 'audio/m4a',
            durationSecs: recordSecs > 0 ? recordSecs : 1,
          },
        ]);
      }
    } catch (err) {
      console.error('Failed to stop recording:', err);
    }
  };

  const toggleRecording = () => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  };

  const removeAttachment = () => {
    setAttachments([]);
  };

  // -------------------------------------------------------------
  // SUBMISSION TO FASTAPI BACKEND
  // -------------------------------------------------------------
  const handleStartSave = () => {
    if (!inputText.trim() && attachments.length === 0) return;
    setErrorMessage(null);
    setIsPrivacyModalOpen(true);
    // Background fetch groups without blocking modal
    getGroups().then((gList) => {
      setAvailableGroups(gList);
      if (!chosenGroupId && gList.length > 0) {
        setChosenGroupId(gList[0].id);
      }
    }).catch(() => {});
  };

  const handleCancelProcessing = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    setIsProcessing(false);
    setErrorMessage('Ingestion cancelled by user.');
  };

  const handleExecuteSave = async () => {
    // If saving to Private Locker, verify unlock status
    if (selectedDestination === 'locker') {
      if (!lockerExists) {
        Alert.alert('Locker Required', 'Please initialize your Private Locker from the Locker tab first.');
        return;
      }
      if (!isLockerUnlocked) {
        if (!lockerPassword.trim()) {
          setLockerError('Enter your Locker password to authorize private storage.');
          return;
        }
        setIsUnlockingLocker(true);
        try {
          await unlockLocker(lockerPassword.trim());
          setLockerPassword('');
          setLockerError(null);
        } catch (e: any) {
          setIsUnlockingLocker(false);
          setLockerError(e.message || 'Incorrect locker password.');
          return;
        } finally {
          setIsUnlockingLocker(false);
        }
      }
    }

    setIsPrivacyModalOpen(false);
    setIsProcessing(true);
    setProcessingStep(1);
    setErrorMessage(null);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      let memoryV1: MemoryV1;
      let mediaUri: string | undefined;

      const photo = attachments.find((a) => a.type === 'photo');
      const audio = attachments.find((a) => a.type === 'audio');

      if (selectedDestination === 'locker') {
        // -------------------------------------------------------------
        // PATH A: PRIVATE LOCKER — PHONE-ONLY ENCRYPTED PERSISTENCE
        // Never call backend ingestion routes for private content!
        // -------------------------------------------------------------
        setProcessingStep(2);

        // Verify/unlock local device key
        if (!deviceKeyManager.isUnlocked()) {
          if (lockerPassword && lockerPassword.length >= 8) {
            await deviceKeyManager.unlockWithPassword(lockerPassword);
          } else {
            throw new Error('Please enter your locker password to authorize local encrypted storage.');
          }
        }

        const localId = `loc_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
        const localTitle =
          inputText.trim().split('\n')[0].slice(0, 40) ||
          (photo ? 'Private Photo' : audio ? 'Private Audio' : 'Private Note');

        let savedLocalMediaUri: string | undefined;
        if (photo) {
          savedLocalMediaUri = await localEncryptedStorage.saveMediaFile(photo.uri, 'image');
        } else if (audio) {
          savedLocalMediaUri = await localEncryptedStorage.saveMediaFile(audio.uri, 'audio');
        }

        // Store encrypted on phone only (zero server persistence)
        const savedLocal = await localFirstAdapter.savePrivateMemory({
          id: localId,
          text: inputText.trim() || (photo ? '[Private Photo]' : '[Private Audio]'),
          title: localTitle,
          mediaUri: savedLocalMediaUri,
          mediaType: photo ? 'image' : audio ? 'audio' : 'text',
        });

        setProcessingStep(3);

        const convertedItem: MemoryItem = {
          id: savedLocal.id,
          type: photo ? 'photo' : audio ? 'voice' : 'note',
          title: savedLocal.title,
          timestamp: 'Just now',
          dateStr: 'Today',
          timeOfDay: 'afternoon',
          privacy: 'encrypted',
          isEncrypted: true,
          snippet: savedLocal.text.slice(0, 100),
          fullContent: savedLocal.text,
          mediaUrl: savedLocalMediaUri,
          localMediaUri: savedLocalMediaUri,
          tags: ['Private Locker', 'Encrypted', 'Local-Only'],
          entities: [],
          created_at: new Date().toISOString(),
        };

        // Hand off to session state (App.tsx will isolate it from Main Stream)
        onSaveMemory(convertedItem);

        setTimeout(() => {
          setIsProcessing(false);
          onNavigate('locker');
        }, 500);
        return;
      }

      // -------------------------------------------------------------
      // PATH B: MAIN STREAM — SERVER PERSISTENCE
      // Normal ingestion via FastAPI on port 8002
      // -------------------------------------------------------------
      const privacy = toBackendPrivacy(selectedDestination);

      const targetGroupId = selectedDestination === 'group' ? (chosenGroupId || initialGroupId || null) : null;

      if (audio) {
        setProcessingStep(2);
        mediaUri = audio.uri;
        memoryV1 = await ingestAudioMemory({
          uri: audio.uri,
          name: audio.name,
          type: audio.mimeType,
          context: inputText.trim() || undefined,
          privacy,
          group_id: targetGroupId,
        });
      } else if (photo) {
        setProcessingStep(2);
        mediaUri = photo.uri;
        memoryV1 = await ingestImageMemory({
          uri: photo.uri,
          name: photo.name,
          type: photo.mimeType,
          context: inputText.trim() || undefined,
          privacy,
          group_id: targetGroupId,
        });
      } else {
        setProcessingStep(2);
        memoryV1 = await ingestTextMemory({
          text: inputText.trim(),
          privacy,
          group_id: targetGroupId,
        });
      }

      setProcessingStep(3);

      const convertedItem = convertMemoryV1ToMemoryItem(memoryV1, mediaUri);

      // Save memory to frontend app session state
      onSaveMemory(convertedItem);

      // Transition to Memory Detail
      setTimeout(() => {
        onNavigate('memory_detail');
      }, 400);
    } catch (err: any) {
      console.error('Ingestion error:', err);
      setErrorMessage(err.message || 'Failed to ingest memory. Check backend connectivity.');
    } finally {
      setIsProcessing(false);
      abortControllerRef.current = null;
    }
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <KeyboardAvoidingView
        style={styles.keyboardAvoidingView}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={Platform.OS === 'ios' ? 8 : 0}
      >
        <View style={styles.container}>
          {/* Header with Back and Close */}
          <View style={styles.topHeader}>
            <TouchableOpacity
              style={styles.backButton}
              onPress={() => onNavigate('home')}
              activeOpacity={0.8}
            >
              <Ionicons name="arrow-back" size={18} color="#4A6B53" />
              <Text style={styles.backButtonText}>Feed</Text>
            </TouchableOpacity>

            <View style={styles.headerTitleGroup}>
              <View style={styles.titleRow}>
                <Text style={styles.headerTitle}>Capture Memory</Text>
                <View style={styles.livePill}>
                  <Text style={styles.livePillText}>Phase 1 Live</Text>
                </View>
              </View>
              <Text style={styles.headerSubtitle} numberOfLines={1}>
                Notes, photos, or voice. Extracted with Qwen & stored.
              </Text>
            </View>

            <TouchableOpacity
              style={styles.closeButton}
              onPress={() => onNavigate('home')}
              activeOpacity={0.8}
            >
              <Ionicons name="close" size={18} color="#5E7A64" />
            </TouchableOpacity>
          </View>

          {/* Error Banner */}
          {errorMessage && (
            <View style={styles.errorBanner}>
              <Ionicons name="alert-circle" size={18} color="#DC2626" />
              <View style={styles.errorTextGroup}>
                <Text style={styles.errorTitle}>Ingestion Failed</Text>
                <Text style={styles.errorDesc}>{errorMessage}</Text>
              </View>
              <TouchableOpacity
                style={styles.retryButton}
                onPress={handleExecuteSave}
                activeOpacity={0.8}
              >
                <Text style={styles.retryButtonText}>Retry</Text>
              </TouchableOpacity>
            </View>
          )}

          {/* Main Canvas Scroll Area */}
          <ScrollView
            style={styles.canvasScroll}
            showsVerticalScrollIndicator={false}
            keyboardShouldPersistTaps="handled"
          >
            {/* Neural Thought Buffer Context Card */}
            <View style={styles.contextCard}>
              <View style={styles.contextHeader}>
                <View style={styles.locationTag}>
                  <Ionicons name="location" size={14} color="#4A6B53" />
                  <Text style={styles.locationTagText}>Curlies Shack, Anjuna, Goa</Text>
                </View>
                <Text style={styles.timeTag}>
                  {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </Text>
              </View>

              <Text style={styles.contextTitle}>Neural Thought Buffer</Text>
              <Text style={styles.contextDesc}>
                MindMesh synthesizes context, audio transcripts, photos, and linked memories seamlessly.
              </Text>

              {/* Quick Tag Pills */}
              <View style={styles.tagChipsRow}>
                {['#GoaTrip2026', '#AnjunaSunset', '#Architecture', '#Thoughts'].map((t) => {
                  const cleanTag = t.replace('#', '');
                  const isSelected = selectedTags.includes(cleanTag);
                  return (
                    <TouchableOpacity
                      key={t}
                      onPress={() => {
                        if (isSelected) {
                          setSelectedTags(selectedTags.filter((tag) => tag !== cleanTag));
                        } else {
                          setSelectedTags([...selectedTags, cleanTag]);
                        }
                      }}
                      style={[styles.tagChip, isSelected && styles.tagChipActive]}
                      activeOpacity={0.8}
                    >
                      <Text style={[styles.tagChipText, isSelected && styles.tagChipTextActive]}>
                        {t}
                      </Text>
                    </TouchableOpacity>
                  );
                })}
              </View>
            </View>

            {/* Live Recording Active Banner */}
            {isRecording && (
              <View style={styles.recordingBanner}>
                <View style={styles.recordingHeader}>
                  <View style={styles.recordingDot} />
                  <Text style={styles.recordingTitle}>Microphone Recording Live</Text>
                  <Text style={styles.recordingTime}>
                    00:{recordSecs.toString().padStart(2, '0')}
                  </Text>
                </View>

                <View style={styles.waveVisualizer}>
                  {[14, 28, 44, 22, 50, 36, 18, 42, 30, 48, 20, 32].map((h, i) => (
                    <View
                      key={i}
                      style={[
                        styles.waveBar,
                        { height: Math.max(12, (h * ((recordSecs % 3) + 1)) % 48) },
                      ]}
                    />
                  ))}
                </View>
              </View>
            )}

            {/* Attached Media Tray */}
            {attachments.length > 0 && (
              <View style={styles.attachmentTray}>
                <Text style={styles.attachmentTrayTitle}>Attached Media</Text>
                <View style={styles.attachmentCard}>
                  {attachments[0].type === 'photo' ? (
                    <Image source={{ uri: attachments[0].uri }} style={styles.attachmentThumb} />
                  ) : (
                    <View style={styles.audioIconBox}>
                      <Ionicons name="mic" size={20} color="#4A6B53" />
                    </View>
                  )}

                  <View style={styles.attachmentInfo}>
                    <Text style={styles.attachmentName} numberOfLines={1}>
                      {attachments[0].name}
                    </Text>
                    <Text style={styles.attachmentSub}>
                      {attachments[0].type === 'photo'
                        ? 'Image Attachment'
                        : `Voice Memo (${attachments[0].durationSecs || 1}s)`}
                    </Text>
                  </View>

                  <TouchableOpacity
                    style={styles.removeAttachmentButton}
                    onPress={removeAttachment}
                  >
                    <Ionicons name="close" size={16} color="#DC2626" />
                  </TouchableOpacity>
                </View>
              </View>
            )}
          </ScrollView>

          {/* (+) Popover Menu Sheet */}
          {isMenuOpen && (
            <View style={styles.popoverMenu}>
              <TouchableOpacity
                style={styles.popoverItem}
                onPress={handleTakePhoto}
                activeOpacity={0.8}
              >
                <View style={[styles.popoverIconCircle, { backgroundColor: '#DCFCE7' }]}>
                  <Ionicons name="camera" size={18} color="#16A34A" />
                </View>
                <View>
                  <Text style={styles.popoverItemTitle}>Camera Snapshot</Text>
                  <Text style={styles.popoverItemSubtitle}>Take a live photo</Text>
                </View>
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.popoverItem}
                onPress={handlePickImage}
                activeOpacity={0.8}
              >
                <View style={[styles.popoverIconCircle, { backgroundColor: '#FEF3C7' }]}>
                  <Ionicons name="images" size={18} color="#D97706" />
                </View>
                <View>
                  <Text style={styles.popoverItemTitle}>Photo Gallery</Text>
                  <Text style={styles.popoverItemSubtitle}>Pick from library</Text>
                </View>
              </TouchableOpacity>
            </View>
          )}

          {/* Unified Single Input Bar */}
          <View style={styles.inputBar}>
            {/* Left (+) Button */}
            <TouchableOpacity
              style={[styles.actionIconBtn, isMenuOpen && styles.actionIconBtnActive]}
              onPress={() => setIsMenuOpen(!isMenuOpen)}
              activeOpacity={0.8}
            >
              <Ionicons
                name="add"
                size={22}
                color={isMenuOpen ? '#FFFFFF' : '#5E7A64'}
              />
            </TouchableOpacity>

            {/* Center TextInput */}
            <TextInput
              value={inputText}
              onChangeText={setInputText}
              placeholder={
                isRecording
                  ? 'Recording audio...'
                  : attachments.some((a) => a.type === 'photo')
                  ? 'Add caption context for image...'
                  : attachments.some((a) => a.type === 'audio')
                  ? 'Add context for voice memo...'
                  : 'Add memory, note, or paste thoughts...'
              }
              placeholderTextColor="#8A9E8F"
              style={styles.textInput}
              multiline={false}
            />

            {/* Microphone Recording Button */}
            <TouchableOpacity
              style={[styles.actionIconBtn, isRecording && styles.micBtnRecording]}
              onPress={toggleRecording}
              activeOpacity={0.8}
            >
              <Ionicons
                name={isRecording ? 'square' : 'mic'}
                size={18}
                color={isRecording ? '#FFFFFF' : '#5E7A64'}
              />
            </TouchableOpacity>

            {/* Send Button */}
            <TouchableOpacity
              style={[
                styles.sendButton,
                (inputText.trim() || attachments.length > 0) && styles.sendButtonActive,
              ]}
              onPress={handleStartSave}
              disabled={!inputText.trim() && attachments.length === 0}
              activeOpacity={0.85}
            >
              <Ionicons name="send" size={16} color="#FFFFFF" />
            </TouchableOpacity>
          </View>
        </View>
      </KeyboardAvoidingView>

      {/* Destination & Privacy Modal */}
      <Modal visible={isPrivacyModalOpen} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modalSheet}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Store Memory Destination</Text>
              <TouchableOpacity onPress={() => setIsPrivacyModalOpen(false)}>
                <Ionicons name="close" size={20} color="#5E7A64" />
              </TouchableOpacity>
            </View>

            <Text style={styles.modalSubtitle}>
              Choose where to index and encrypt this memory.
            </Text>

            {/* Private Locker - Password Protected & Encrypted */}
            <TouchableOpacity
              style={[
                styles.destOption,
                selectedDestination === 'locker' && styles.destOptionActive,
              ]}
              onPress={() => setSelectedDestination('locker')}
              activeOpacity={0.8}
            >
              <View style={[styles.destIconBox, { backgroundColor: '#E8F5E9' }]}>
                <Ionicons name="lock-closed" size={18} color="#2D5A27" />
              </View>
              <View style={styles.destInfo}>
                <Text style={styles.destTitle}>Private Locker (Secured)</Text>
                <Text style={styles.destDesc}>
                  AES-256-GCM encrypted. Hidden behind password & auto-lock.
                </Text>
              </View>
              {selectedDestination === 'locker' && (
                <Ionicons name="checkmark-circle" size={20} color="#2D5A27" />
              )}
            </TouchableOpacity>

            {/* Inline Locker Unlock Prompt if locked */}
            {selectedDestination === 'locker' && !isLockerUnlocked && (
              <View style={styles.lockerUnlockBox}>
                {!lockerExists ? (
                  <Text style={styles.lockerUnlockHint}>
                    Private Locker is not initialized. Please set it up in the Locker tab first.
                  </Text>
                ) : (
                  <>
                    <View style={styles.lockerUnlockHeader}>
                      <Ionicons name="lock-closed" size={14} color="#D97706" />
                      <Text style={styles.lockerUnlockHint}>
                        Locker locked. Enter password to authorize private storage:
                      </Text>
                    </View>
                    <TextInput
                      style={styles.lockerInlineInput}
                      placeholder="Locker Password"
                      placeholderTextColor="#999"
                      secureTextEntry
                      value={lockerPassword}
                      onChangeText={(t) => {
                        setLockerPassword(t);
                        setLockerError(null);
                      }}
                    />
                    {lockerError ? (
                      <Text style={styles.lockerInlineError}>{lockerError}</Text>
                    ) : null}
                  </>
                )}
              </View>
            )}

            <TouchableOpacity
              style={[
                styles.destOption,
                selectedDestination === 'private' && styles.destOptionActive,
              ]}
              onPress={() => setSelectedDestination('private')}
              activeOpacity={0.8}
            >
              <View style={styles.destIconBox}>
                <Ionicons name="shield-checkmark" size={18} color="#4A6B53" />
              </View>
              <View style={styles.destInfo}>
                <Text style={styles.destTitle}>Personal Vault (Only Me)</Text>
                <Text style={styles.destDesc}>
                  Visible only to you in standard stream and search.
                </Text>
              </View>
              {selectedDestination === 'private' && (
                <Ionicons name="checkmark-circle" size={20} color="#4A6B53" />
              )}
            </TouchableOpacity>

            <TouchableOpacity
              style={[
                styles.destOption,
                selectedDestination === 'group' && styles.destOptionActive,
              ]}
              onPress={() => setSelectedDestination('group')}
              activeOpacity={0.8}
            >
              <View style={styles.destIconBox}>
                <Ionicons name="people" size={18} color="#4A6B53" />
              </View>
              <View style={styles.destInfo}>
                <Text style={styles.destTitle}>Group Stream</Text>
                <Text style={styles.destDesc}>
                  Shared with your selected group or squad.
                </Text>
              </View>
              {selectedDestination === 'group' && (
                <Ionicons name="checkmark-circle" size={20} color="#4A6B53" />
              )}
            </TouchableOpacity>

            {selectedDestination === 'group' && availableGroups.length > 0 && (
              <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginVertical: 8, paddingLeft: 4 }}>
                {availableGroups.map((g) => (
                  <TouchableOpacity
                    key={g.id}
                    onPress={() => setChosenGroupId(g.id)}
                    style={{
                      paddingVertical: 6,
                      paddingHorizontal: 12,
                      borderRadius: 14,
                      backgroundColor: chosenGroupId === g.id ? '#4A6B53' : '#FAF7F0',
                      borderWidth: 1,
                      borderColor: chosenGroupId === g.id ? '#4A6B53' : '#D5CDBC',
                      marginRight: 8,
                    }}
                  >
                    <Text
                      style={{
                        fontSize: 12,
                        fontWeight: '700',
                        color: chosenGroupId === g.id ? '#FFFFFF' : '#1F2923',
                      }}
                    >
                      {g.name}
                    </Text>
                  </TouchableOpacity>
                ))}
              </ScrollView>
            )}

            <TouchableOpacity
              style={[
                styles.destOption,
                selectedDestination === 'public' && styles.destOptionActive,
              ]}
              onPress={() => setSelectedDestination('public')}
              activeOpacity={0.8}
            >
              <View style={styles.destIconBox}>
                <Ionicons name="globe-outline" size={18} color="#4A6B53" />
              </View>
              <View style={styles.destInfo}>
                <Text style={styles.destTitle}>General Stream</Text>
                <Text style={styles.destDesc}>
                  Personal memory stored in your default feed (Only Me).
                </Text>
              </View>
              {selectedDestination === 'public' && (
                <Ionicons name="checkmark-circle" size={20} color="#4A6B53" />
              )}
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.confirmSaveButton}
              onPress={handleExecuteSave}
              activeOpacity={0.88}
            >
              <Text style={styles.confirmSaveText}>Send to Qwen Phase 1</Text>
              <Ionicons name="arrow-forward" size={16} color="#FFFFFF" />
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      {/* Processing Extraction Modal Overlay */}
      <Modal visible={isProcessing} transparent animationType="fade">
        <View style={styles.modalOverlay}>
          <View style={styles.processingCard}>
            <View style={styles.processingSpinnerCircle}>
              <ActivityIndicator size="large" color="#4A6B53" />
            </View>

            <Text style={styles.processingTitle}>Extracting Phase 1 Memory</Text>
            <Text style={styles.processingSubtitle}>
              Qwen 3.8-27B is extracting entities, semantics, and temporal facts...
            </Text>

            {/* Progress Steps List */}
            <View style={styles.stepList}>
              <View style={styles.stepRow}>
                <Ionicons
                  name={processingStep >= 1 ? 'checkmark-circle' : 'ellipse-outline'}
                  size={16}
                  color={processingStep >= 1 ? '#16A34A' : '#8A9E8F'}
                />
                <Text
                  style={[
                    styles.stepText,
                    processingStep >= 1 && styles.stepTextActive,
                  ]}
                >
                  1. Validating payload & transmitting to FastAPI
                </Text>
              </View>

              <View style={styles.stepRow}>
                <Ionicons
                  name={processingStep >= 2 ? 'checkmark-circle' : 'ellipse-outline'}
                  size={16}
                  color={processingStep >= 2 ? '#16A34A' : '#8A9E8F'}
                />
                <Text
                  style={[
                    styles.stepText,
                    processingStep >= 2 && styles.stepTextActive,
                  ]}
                >
                  2. Qwen Phase 1 structured extraction
                </Text>
              </View>

              <View style={styles.stepRow}>
                <Ionicons
                  name={processingStep >= 3 ? 'checkmark-circle' : 'ellipse-outline'}
                  size={16}
                  color={processingStep >= 3 ? '#16A34A' : '#8A9E8F'}
                />
                <Text
                  style={[
                    styles.stepText,
                    processingStep >= 3 && styles.stepTextActive,
                  ]}
                >
                  3. PostgreSQL persistence (MemoryV1)
                </Text>
              </View>
            </View>

            {/* Cancel Processing Action */}
            <TouchableOpacity
              style={styles.cancelProcessingBtn}
              onPress={handleCancelProcessing}
              activeOpacity={0.8}
            >
              <Text style={styles.cancelProcessingBtnText}>Cancel Ingestion</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#FAF7F0',
  },
  keyboardAvoidingView: {
    flex: 1,
  },
  container: {
    flex: 1,
    paddingHorizontal: 16,
    paddingTop: 8,
    justifyContent: 'space-between',
  },
  topHeader: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#E5DFD5',
  },
  titleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '800',
    color: '#233529',
  },
  livePill: {
    backgroundColor: '#EFEAE1',
    paddingVertical: 2,
    paddingHorizontal: 8,
    borderRadius: 12,
  },
  livePillText: {
    fontSize: 10,
    fontWeight: '800',
    color: '#4A6B53',
  },
  headerSubtitle: {
    fontSize: 11,
    color: '#5E7A64',
    marginTop: 3,
    maxWidth: 280,
  },
  closeButton: {
    width: 32,
    height: 32,
    borderRadius: 10,
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#D5CDBC',
    alignItems: 'center',
    justifyContent: 'center',
  },
  errorBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FEE2E2',
    borderWidth: 1,
    borderColor: '#FCA5A5',
    borderRadius: 16,
    padding: 12,
    marginVertical: 8,
    gap: 10,
  },
  errorTextGroup: {
    flex: 1,
  },
  errorTitle: {
    fontSize: 12,
    fontWeight: '700',
    color: '#991B1B',
  },
  errorDesc: {
    fontSize: 10,
    color: '#B91C1C',
    marginTop: 2,
  },
  retryButton: {
    backgroundColor: '#DC2626',
    paddingVertical: 5,
    paddingHorizontal: 10,
    borderRadius: 8,
  },
  retryButtonText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  canvasScroll: {
    flex: 1,
    marginVertical: 10,
  },
  contextCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    padding: 16,
    borderWidth: 1,
    borderColor: '#E5DFD5',
    gap: 8,
  },
  contextHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  locationTag: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  locationTagText: {
    fontSize: 11,
    fontWeight: '600',
    color: '#4A6B53',
  },
  timeTag: {
    fontSize: 10,
    color: '#5E7A64',
    fontWeight: '600',
  },
  contextTitle: {
    fontSize: 13,
    fontWeight: '800',
    color: '#233529',
    marginTop: 2,
  },
  contextDesc: {
    fontSize: 11,
    color: '#5E7A64',
    lineHeight: 16,
  },
  tagChipsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    marginTop: 6,
  },
  tagChip: {
    paddingVertical: 4,
    paddingHorizontal: 9,
    borderRadius: 8,
    backgroundColor: '#FAF7F0',
    borderWidth: 1,
    borderColor: '#D5CDBC',
  },
  tagChipActive: {
    backgroundColor: '#4A6B53',
    borderColor: '#4A6B53',
  },
  tagChipText: {
    fontSize: 10,
    fontWeight: '700',
    color: '#5E7A64',
  },
  tagChipTextActive: {
    color: '#FFFFFF',
  },
  recordingBanner: {
    backgroundColor: '#FEE2E2',
    borderRadius: 18,
    borderWidth: 1,
    borderColor: '#F87171',
    padding: 14,
    marginTop: 12,
    gap: 10,
  },
  recordingHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  recordingDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: '#DC2626',
  },
  recordingTitle: {
    fontSize: 12,
    fontWeight: '700',
    color: '#DC2626',
    flex: 1,
    marginLeft: 8,
  },
  recordingTime: {
    fontSize: 12,
    fontWeight: '800',
    color: '#DC2626',
    fontFamily: 'System',
  },
  waveVisualizer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 4,
    height: 48,
  },
  waveBar: {
    width: 4,
    backgroundColor: '#DC2626',
    borderRadius: 2,
  },
  attachmentTray: {
    marginTop: 12,
    gap: 6,
  },
  attachmentTrayTitle: {
    fontSize: 10,
    fontWeight: '800',
    color: '#5E7A64',
    textTransform: 'uppercase',
    letterSpacing: 0.8,
  },
  attachmentCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderRadius: 14,
    padding: 10,
    borderWidth: 1,
    borderColor: '#D5CDBC',
    gap: 10,
  },
  attachmentThumb: {
    width: 42,
    height: 42,
    borderRadius: 8,
  },
  audioIconBox: {
    width: 42,
    height: 42,
    borderRadius: 8,
    backgroundColor: '#FAF7F0',
    alignItems: 'center',
    justifyContent: 'center',
  },
  attachmentInfo: {
    flex: 1,
  },
  attachmentName: {
    fontSize: 12,
    fontWeight: '700',
    color: '#233529',
  },
  attachmentSub: {
    fontSize: 10,
    color: '#5E7A64',
    marginTop: 2,
  },
  removeAttachmentButton: {
    padding: 6,
    backgroundColor: '#FEE2E2',
    borderRadius: 8,
  },
  popoverMenu: {
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    padding: 12,
    borderWidth: 1,
    borderColor: '#D5CDBC',
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 12,
    elevation: 8,
    marginBottom: 8,
    gap: 8,
  },
  popoverItem: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 8,
    borderRadius: 12,
    gap: 10,
  },
  popoverIconCircle: {
    width: 36,
    height: 36,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  popoverItemTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: '#233529',
  },
  popoverItemSubtitle: {
    fontSize: 10,
    color: '#5E7A64',
  },
  inputBar: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderRadius: 22,
    borderWidth: 1.5,
    borderColor: '#D5CDBC',
    paddingHorizontal: 8,
    paddingVertical: 6,
    marginBottom: 10,
    gap: 6,
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.08,
    shadowRadius: 8,
    elevation: 4,
  },
  actionIconBtn: {
    width: 36,
    height: 36,
    borderRadius: 12,
    backgroundColor: '#FAF7F0',
    alignItems: 'center',
    justifyContent: 'center',
  },
  actionIconBtnActive: {
    backgroundColor: '#4A6B53',
  },
  micBtnRecording: {
    backgroundColor: '#DC2626',
  },
  textInput: {
    flex: 1,
    fontSize: 13,
    color: '#233529',
    paddingHorizontal: 6,
  },
  sendButton: {
    width: 36,
    height: 36,
    borderRadius: 12,
    backgroundColor: '#D5CDBC',
    alignItems: 'center',
    justifyContent: 'center',
  },
  sendButtonActive: {
    backgroundColor: '#4A6B53',
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  modalSheet: {
    width: '100%',
    backgroundColor: '#FFFFFF',
    borderRadius: 24,
    padding: 20,
    gap: 12,
    borderWidth: 1,
    borderColor: '#D5CDBC',
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  modalTitle: {
    fontSize: 16,
    fontWeight: '800',
    color: '#233529',
  },
  modalSubtitle: {
    fontSize: 12,
    color: '#5E7A64',
  },
  destOption: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    borderRadius: 16,
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#E5DFD5',
    gap: 12,
  },
  destOptionActive: {
    backgroundColor: '#FAF7F0',
    borderColor: '#4A6B53',
    borderWidth: 1.5,
  },
  destIconBox: {
    width: 36,
    height: 36,
    borderRadius: 10,
    backgroundColor: '#FAF7F0',
    alignItems: 'center',
    justifyContent: 'center',
  },
  destInfo: {
    flex: 1,
  },
  destTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: '#233529',
  },
  destDesc: {
    fontSize: 10,
    color: '#5E7A64',
    marginTop: 2,
  },
  confirmSaveButton: {
    backgroundColor: '#4A6B53',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 14,
    borderRadius: 16,
    gap: 8,
    marginTop: 6,
  },
  confirmSaveText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '700',
  },
  processingCard: {
    width: '90%',
    backgroundColor: '#FFFFFF',
    borderRadius: 24,
    padding: 24,
    alignItems: 'center',
    gap: 12,
    borderWidth: 1,
    borderColor: '#D5CDBC',
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.15,
    shadowRadius: 16,
    elevation: 8,
  },
  processingSpinnerCircle: {
    width: 64,
    height: 64,
    borderRadius: 20,
    backgroundColor: '#FAF7F0',
    alignItems: 'center',
    justifyContent: 'center',
  },
  processingTitle: {
    fontSize: 17,
    fontWeight: '800',
    color: '#233529',
  },
  processingSubtitle: {
    fontSize: 11,
    color: '#5E7A64',
    textAlign: 'center',
    lineHeight: 16,
  },
  stepList: {
    width: '100%',
    backgroundColor: '#FAF7F0',
    padding: 14,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#E5DFD5',
    gap: 10,
    marginTop: 4,
  },
  stepRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  stepText: {
    fontSize: 11,
    color: '#5E7A64',
    fontWeight: '500',
    flex: 1,
  },
  stepTextActive: {
    color: '#233529',
    fontWeight: '700',
  },
  backButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingVertical: 6,
    paddingHorizontal: 8,
    borderRadius: 10,
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#D5CDBC',
  },
  backButtonText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#4A6B53',
  },
  headerTitleGroup: {
    flex: 1,
    marginHorizontal: 10,
  },
  lockerUnlockBox: {
    backgroundColor: '#FFFBEB',
    borderRadius: 12,
    padding: 12,
    borderWidth: 1,
    borderColor: '#FDE68A',
    gap: 8,
    marginTop: 2,
  },
  lockerUnlockHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  lockerUnlockHint: {
    fontSize: 11,
    color: '#92400E',
    fontWeight: '600',
    lineHeight: 15,
  },
  lockerInlineInput: {
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#FCD34D',
    borderRadius: 8,
    paddingVertical: 8,
    paddingHorizontal: 12,
    fontSize: 13,
    color: '#233529',
  },
  lockerInlineError: {
    fontSize: 11,
    color: '#DC2626',
    fontWeight: '600',
  },
  cancelProcessingBtn: {
    marginTop: 10,
    paddingVertical: 10,
    paddingHorizontal: 22,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#D5CDBC',
    backgroundColor: '#FAF7F0',
  },
  cancelProcessingBtnText: {
    fontSize: 13,
    fontWeight: '700',
    color: '#5E7A64',
  },
});
