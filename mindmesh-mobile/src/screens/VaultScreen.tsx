import React, { useState, useRef, useEffect } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  Image,
  StyleSheet,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { MindMeshLogo } from '../components/MindMeshLogo';
import { FloatingBottomDock } from '../components/FloatingBottomDock';
import { MemoryItem, ScreenId, SearchResultItem, Group } from '../types';
import { searchMemories, searchNearbyMemories, getGroups } from '../services/apiClient';
import { convertSearchResultToMemoryItem } from '../services/memoryAdapter';
import { getApiUrl } from '../config/apiConfig';
import { useAuth } from '../auth/AuthContext';

interface VaultTurn {
  id: string;
  query: string;
  timestamp: string;
  isLoading: boolean;
  error?: string | null;
  radiusKm?: number | null;
  locationName?: string | null;
  response?: {
    query: string;
    answer?: string | null;
    grounded?: boolean;
    results: SearchResultItem[];
    total_results?: number;
  } | null;
}

interface VaultProps {
  onNavigate: (id: ScreenId) => void;
  onSelectMemory: (memory: MemoryItem) => void;
}

const SUGGESTED_QUERIES = [
  'What did I do in Goa?',
  'Where did I have coffee recently?',
  'Did I meet with anyone this week?',
  'What are my key project updates?',
];

export const VaultScreen: React.FC<VaultProps> = ({
  onNavigate,
  onSelectMemory,
}) => {
  const { user } = useAuth();
  const [inputText, setInputText] = useState('');
  const [conversation, setConversation] = useState<VaultTurn[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [availableGroups, setAvailableGroups] = useState<Group[]>([]);
  const [selectedGroupId, setSelectedGroupId] = useState<string | null>(null);
  const scrollViewRef = useRef<ScrollView>(null);
  // Distance Radius (0 to 15 km) & Location-aware state
  const [radiusKm, setRadiusKm] = useState<number | null>(null); // null = Global / Off
  const [selectedPlace, setSelectedPlace] = useState('Dehradun');
  const [locationQuery, setLocationQuery] = useState('Dehradun');
  const [searchMode, setSearchMode] = useState<'hybrid' | 'nearby' | 'graph' | 'vector'>('hybrid');

  useEffect(() => {
    getGroups().then(setAvailableGroups).catch(() => {});
  }, []);

  const handleSendQuery = async (textToSend?: string) => {
    const q = (textToSend !== undefined ? textToSend : inputText).trim();
    if (!q || isSearching) return;

    setInputText('');
    const turnId = `turn-${Date.now()}`;
    const newTurn: VaultTurn = {
      id: turnId,
      query: q,
      timestamp: new Date().toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
      }),
      isLoading: true,
      error: null,
      radiusKm: radiusKm,
      locationName: radiusKm !== null ? (locationQuery.trim() || selectedPlace) : null,
      response: null,
    };

    setConversation((prev) => [...prev, newTurn]);
    setIsSearching(true);

    // Auto-scroll to bottom
    setTimeout(() => {
      scrollViewRef.current?.scrollToEnd({ animated: true });
    }, 100);

    try {
      const locationParams: Record<string, any> = { mode: searchMode };
      if (radiusKm !== null && radiusKm > 0) {
        locationParams.radius_km = radiusKm;
        locationParams.location_query = locationQuery.trim() || selectedPlace || 'Dehradun';
      }
      const response = await searchMemories({
        query: q,
        top_k: 5,
        content_weight: 0.5,
        context_weight: 0.5,
        generate_answer: true,
        group_id: selectedGroupId || undefined,
        ...locationParams,
      });

      setConversation((prev) =>
        prev.map((turn) =>
          turn.id === turnId
            ? { ...turn, isLoading: false, response: response as any }
            : turn
        )
      );
    } catch (err: any) {
      console.error('Vault search error:', err);
      setConversation((prev) =>
        prev.map((turn) =>
          turn.id === turnId
            ? {
                ...turn,
                isLoading: false,
                error:
                  err?.message ||
                  'Failed to query memory vault. Please verify server connection.',
              }
            : turn
        )
      );
    } finally {
      setIsSearching(false);
      setTimeout(() => {
        scrollViewRef.current?.scrollToEnd({ animated: true });
      }, 150);
    }
  };

  const handleRerunQueryWithRadius = async (newRadius?: number | null, newLocation?: string) => {
    if (conversation.length === 0 || isSearching) return;
    const lastTurn = conversation[conversation.length - 1];
    const q = lastTurn.query;
    const rKm = newRadius !== undefined ? newRadius : radiusKm;
    const loc = newLocation !== undefined ? newLocation : (locationQuery.trim() || selectedPlace || 'Dehradun');

    // Update the last turn to loading state
    setConversation((prev) =>
      prev.map((turn, i) =>
        i === prev.length - 1
          ? {
              ...turn,
              isLoading: true,
              radiusKm: rKm,
              locationName: rKm !== null ? loc : null,
              error: null,
            }
          : turn
      )
    );
    setIsSearching(true);

    try {
      const locationParams: Record<string, any> = { mode: searchMode };
      if (rKm !== null && rKm > 0) {
        locationParams.radius_km = rKm;
        locationParams.location_query = loc;
      }
      const response = await searchMemories({
        query: q,
        top_k: 5,
        content_weight: 0.5,
        context_weight: 0.5,
        generate_answer: true,
        group_id: selectedGroupId || undefined,
        ...locationParams,
      });

      setConversation((prev) =>
        prev.map((turn, i) =>
          i === prev.length - 1
            ? { ...turn, isLoading: false, response: response as any }
            : turn
        )
      );
    } catch (err: any) {
      console.error('Vault re-search error:', err);
      setConversation((prev) =>
        prev.map((turn, i) =>
          i === prev.length - 1
            ? {
                ...turn,
                isLoading: false,
                error:
                  err?.message ||
                  'Failed to query memory vault. Please verify server connection.',
              }
            : turn
        )
      );
    } finally {
      setIsSearching(false);
    }
  };

  const handleClearConversation = () => {
    setConversation([]);
    setInputText('');
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <KeyboardAvoidingView
        style={styles.container}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        {/* Top Header with Back to Stream */}
        <View style={styles.topHeader}>
          <TouchableOpacity
            style={styles.backButton}
            onPress={() => onNavigate('home')}
            activeOpacity={0.8}
          >
            <Ionicons name="arrow-back" size={18} color="#4A6B53" />
            <Text style={styles.backButtonText}>Stream</Text>
          </TouchableOpacity>

          <View style={styles.logoGroup}>
            <MindMeshLogo size="sm" withText={false} />
            <View>
              <Text style={styles.headerTitle}>Memory Vault</Text>
              <Text style={styles.headerSubtitle}>Conversational RAG</Text>
            </View>
          </View>

          <View style={styles.headerActionGroup}>
            {conversation.length > 0 && (
              <TouchableOpacity
                style={styles.clearConvButton}
                onPress={handleClearConversation}
                activeOpacity={0.8}
              >
                <Ionicons name="trash-outline" size={16} color="#5E7A64" />
                <Text style={styles.clearConvText}>Clear</Text>
              </TouchableOpacity>
            )}
            <View style={styles.avatarCircle}>
              <Text style={styles.avatarInitial}>
                {(user?.name || user?.email || 'U')[0].toUpperCase()}
              </Text>
            </View>
          </View>
        </View>

        {/* Group Filter Chips */}
        {availableGroups.length > 0 && (
          <View style={styles.groupFilterBar}>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.groupFilterScroll}>
              <TouchableOpacity
                style={[
                  styles.groupFilterChip,
                  selectedGroupId === null && styles.groupFilterChipActive,
                ]}
                onPress={() => setSelectedGroupId(null)}
              >
                <Text
                  style={[
                    styles.groupFilterText,
                    selectedGroupId === null && styles.groupFilterTextActive,
                  ]}
                >
                  All Memories
                </Text>
              </TouchableOpacity>
              {availableGroups.map((g) => (
                <TouchableOpacity
                  key={g.id}
                  style={[
                    styles.groupFilterChip,
                    selectedGroupId === g.id && styles.groupFilterChipActive,
                  ]}
                  onPress={() => setSelectedGroupId(selectedGroupId === g.id ? null : g.id)}
                >
                  <Ionicons
                    name="people"
                    size={12}
                    color={selectedGroupId === g.id ? '#FFFFFF' : '#4A6B53'}
                  />
                  <Text
                    style={[
                      styles.groupFilterText,
                      selectedGroupId === g.id && styles.groupFilterTextActive,
                    ]}
                  >
                    {g.name}
                  </Text>
                </TouchableOpacity>
              ))}
            </ScrollView>
          </View>
        )}

        {/* Distance Radius Bar (0 to 15 km) & Location Scope */}
        <View style={styles.radiusControlContainer}>
          <View style={styles.radiusHeaderRow}>
            <View style={styles.radiusTitleGroup}>
              <Ionicons
                name={radiusKm !== null ? 'radio-outline' : 'globe-outline'}
                size={16}
                color={radiusKm !== null ? '#2D5A3D' : '#5E7A64'}
              />
              <Text style={styles.radiusTitleText}>
                {radiusKm !== null
                  ? `Search Radius: ${radiusKm} km around ${locationQuery.trim() || selectedPlace}`
                  : 'Search Scope: Global (Worldwide)'}
              </Text>
            </View>

            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
              {conversation.length > 0 && (
                <TouchableOpacity
                  style={styles.reSearchBtn}
                  onPress={() => handleRerunQueryWithRadius(radiusKm, locationQuery.trim() || selectedPlace)}
                  activeOpacity={0.8}
                  disabled={isSearching}
                >
                  <Ionicons name="refresh" size={12} color="#FFFFFF" />
                  <Text style={styles.reSearchBtnText}>Re-search</Text>
                </TouchableOpacity>
              )}
              <TouchableOpacity
                style={[
                  styles.radiusToggleBtn,
                  radiusKm !== null && styles.radiusToggleBtnActive,
                ]}
                onPress={() => {
                  const nextVal = radiusKm !== null ? null : 10;
                  setRadiusKm(nextVal);
                  if (conversation.length > 0) {
                    handleRerunQueryWithRadius(nextVal, locationQuery.trim() || selectedPlace);
                  }
                }}
                activeOpacity={0.8}
              >
                <Text
                  style={[
                    styles.radiusToggleText,
                    radiusKm !== null && styles.radiusToggleTextActive,
                  ]}
                >
                  {radiusKm !== null ? 'Reset to Global' : 'Enable Radius'}
                </Text>
              </TouchableOpacity>
            </View>
          </View>

          {/* Preset Radius Pills (0 to 15 km) */}
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.radiusPillsRow}
          >
            {[
              { label: '🌐 Global', value: null },
              { label: '1 km', value: 1 },
              { label: '3 km', value: 3 },
              { label: '5 km', value: 5 },
              { label: '10 km', value: 10 },
              { label: '15 km', value: 15 },
            ].map((p) => {
              const isActive =
                (p.value === null && radiusKm === null) ||
                (p.value !== null && radiusKm === p.value);
              return (
                <TouchableOpacity
                  key={p.label}
                  style={[styles.radiusPill, isActive && styles.radiusPillActive]}
                  onPress={() => {
                    setRadiusKm(p.value);
                    if (conversation.length > 0) {
                      handleRerunQueryWithRadius(p.value, locationQuery.trim() || selectedPlace);
                    }
                  }}
                  activeOpacity={0.8}
                >
                  <Text
                    style={[
                      styles.radiusPillText,
                      isActive && styles.radiusPillTextActive,
                    ]}
                  >
                    {p.label}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </ScrollView>

          {/* Stepper + Place Chips when radius is active */}
          {radiusKm !== null && (
            <View style={styles.activeRadiusSection}>
              {/* Stepper Slider Bar */}
              <View style={styles.stepperRow}>
                <TouchableOpacity
                  style={[styles.stepBtn, radiusKm <= 1 && styles.stepBtnDisabled]}
                  onPress={() => {
                    const nextVal = Math.max(1, (radiusKm || 1) - 1);
                    setRadiusKm(nextVal);
                    if (conversation.length > 0) {
                      handleRerunQueryWithRadius(nextVal, locationQuery.trim() || selectedPlace);
                    }
                  }}
                  disabled={radiusKm <= 1}
                >
                  <Ionicons name="remove" size={16} color="#2D5A3D" />
                </TouchableOpacity>

                <View style={styles.sliderTrackContainer}>
                  <View style={styles.sliderTrackBackground}>
                    <View
                      style={[
                        styles.sliderTrackFill,
                        { width: `${Math.min(100, Math.max(0, (radiusKm / 15) * 100))}%` },
                      ]}
                    />
                  </View>
                  <Text style={styles.sliderValueText}>
                    📍 {radiusKm} km radius (0 to 15 km range)
                  </Text>
                </View>

                <TouchableOpacity
                  style={[styles.stepBtn, radiusKm >= 15 && styles.stepBtnDisabled]}
                  onPress={() => {
                    const nextVal = Math.min(15, (radiusKm || 1) + 1);
                    setRadiusKm(nextVal);
                    if (conversation.length > 0) {
                      handleRerunQueryWithRadius(nextVal, locationQuery.trim() || selectedPlace);
                    }
                  }}
                  disabled={radiusKm >= 15}
                >
                  <Ionicons name="add" size={16} color="#2D5A3D" />
                </TouchableOpacity>
              </View>

              {/* Quick Place Selection Chips */}
              <View style={styles.placeChipsRow}>
                <Text style={styles.placeChipsLabel}>Center on:</Text>
                {['Dehradun', 'Goa', 'Pune', 'Delhi', 'Indiranagar'].map((city) => (
                  <TouchableOpacity
                    key={city}
                    style={[
                      styles.placeChip,
                      locationQuery === city && styles.placeChipActive,
                    ]}
                    onPress={() => {
                      setSelectedPlace(city);
                      setLocationQuery(city);
                      if (conversation.length > 0) {
                        handleRerunQueryWithRadius(radiusKm, city);
                      }
                    }}
                  >
                    <Text
                      style={[
                        styles.placeChipText,
                        locationQuery === city && styles.placeChipTextActive,
                      ]}
                    >
                      {city}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>

              {/* Custom Location Text Input */}
              <View style={styles.customLocationInputBox}>
                <Ionicons name="location-outline" size={15} color="#4A6B53" />
                <TextInput
                  value={locationQuery}
                  onChangeText={setLocationQuery}
                  onSubmitEditing={() => {
                    if (conversation.length > 0) {
                      handleRerunQueryWithRadius(radiusKm, locationQuery.trim() || selectedPlace);
                    }
                  }}
                  returnKeyType="search"
                  placeholder="Or enter custom place (e.g. Dehradun, Goa, Pune)"
                  placeholderTextColor="#8A9E8F"
                  style={styles.customLocationInput}
                />
                {conversation.length > 0 && (
                  <TouchableOpacity
                    style={styles.customLocationApplyBtn}
                    onPress={() => handleRerunQueryWithRadius(radiusKm, locationQuery.trim() || selectedPlace)}
                    activeOpacity={0.8}
                  >
                    <Text style={styles.customLocationApplyText}>Apply</Text>
                  </TouchableOpacity>
                )}
              </View>
            </View>
          )}
        </View>

        {/* Conversation Stream */}
        <ScrollView
          ref={scrollViewRef}
          style={styles.chatScroll}
          contentContainerStyle={styles.chatScrollContent}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
        >
          {conversation.length === 0 ? (
            /* Empty State / Suggested Queries */
            <View style={styles.emptyContainer}>
              <View style={styles.emptyIconCircle}>
                <Ionicons name="sparkles" size={32} color="#4A6B53" />
              </View>
              <Text style={styles.emptyTitle}>Ask Your Memories</Text>
              <Text style={styles.emptySubtitle}>
                Ask natural questions about your past voice memos, photos, places, conversations, and notes.
              </Text>

              <View style={styles.suggestionsBox}>
                <Text style={styles.suggestionsHeader}>SUGGESTED QUESTIONS</Text>
                {SUGGESTED_QUERIES.map((sq, idx) => (
                  <TouchableOpacity
                    key={idx}
                    style={styles.suggestionChip}
                    onPress={() => handleSendQuery(sq)}
                    activeOpacity={0.8}
                  >
                    <Ionicons name="chatbubble-ellipses-outline" size={15} color="#4A6B53" />
                    <Text style={styles.suggestionText}>{sq}</Text>
                    <Ionicons name="arrow-forward" size={14} color="#8A9E8F" />
                  </TouchableOpacity>
                ))}
              </View>
            </View>
          ) : (
            /* Conversation Exchanges */
            conversation.map((turn) => {
              const isGrounded =
                turn.response &&
                turn.response.grounded !== false &&
                turn.response.results &&
                turn.response.results.length > 0;

              return (
                <View key={turn.id} style={styles.turnBlock}>
                  {/* User Query Bubble */}
                  <View style={styles.userBubbleContainer}>
                    <View style={styles.userBubble}>
                      <Text style={styles.userBubbleText}>{turn.query}</Text>
                      {turn.radiusKm ? (
                        <View style={styles.turnRadiusBadge}>
                          <Ionicons name="navigate-circle" size={11} color="#2D5A3D" />
                          <Text style={styles.turnRadiusBadgeText}>
                            Within {turn.radiusKm} km of {turn.locationName || 'Dehradun'}
                          </Text>
                        </View>
                      ) : null}
                      <Text style={styles.userBubbleTime}>{turn.timestamp}</Text>
                    </View>
                  </View>

                  {/* Loading State */}
                  {turn.isLoading && (
                    <View style={styles.loadingCard}>
                      <ActivityIndicator size="small" color="#4A6B53" />
                      <View style={{ flex: 1 }}>
                        <Text style={styles.loadingTitle}>Finding relevant memories...</Text>
                        <Text style={styles.loadingSub}>
                          Retrieving memories and synthesizing answer
                        </Text>
                      </View>
                    </View>
                  )}

                  {/* Error State */}
                  {turn.error && (
                    <View style={styles.errorCard}>
                      <Ionicons name="alert-circle" size={20} color="#D9534F" />
                      <Text style={styles.errorText}>{turn.error}</Text>
                    </View>
                  )}

                  {/* AI Grounded Answer Card */}
                  {turn.response && !turn.isLoading && (
                    <>
                      {isGrounded ? (
                        <>
                          <View style={styles.answerCard}>
                            <View style={styles.answerHeader}>
                              <View style={styles.answerBadge}>
                                <Ionicons name="sparkles" size={14} color="#FFFFFF" />
                                <Text style={styles.answerBadgeText}>AI GROUNDED ANSWER</Text>
                              </View>
                            </View>

                            <Text style={styles.answerBody}>
                              {turn.response.answer && turn.response.answer.trim()
                                ? turn.response.answer
                                : 'No direct answer generated.'}
                            </Text>

                            <View style={styles.answerFooter}>
                              <Ionicons name="shield-checkmark" size={13} color="#4A6B53" />
                              <Text style={styles.answerFooterText}>
                                Grounded in your sovereign memories
                              </Text>
                            </View>
                          </View>

                          {/* Supporting Evidence Header */}
                          <View style={styles.sourcesHeaderRow}>
                            <Text style={styles.sourcesTitle}>
                              SUPPORTING MEMORIES ({turn.response.results.length})
                            </Text>
                          </View>

                          {/* Supporting Memory Cards */}
                          {turn.response.results.map((item: any, sIdx: number) => {
                            const mem = item.memory || item;
                            const mediaType =
                              mem.system?.media_type ||
                              item.source_modality?.toLowerCase() ||
                              'text';
                            const userContext = mem.user_context || item.user_context;
                            const contentText =
                              mem.content?.summary ||
                              mem.content?.description ||
                              mem.content?.clean_text ||
                              mem.content?.raw_text ||
                              item.summary ||
                              item.clean_text ||
                              '';
                            const originalFilename =
                              mem.media?.original_filename ||
                              mem.system?.media_reference ||
                              mem.media?.relative_path ||
                              (item.media ? item.media.original_filename : undefined);

                            const storageKey =
                              mem.media?.storage_key ||
                              mem.system?.media_reference ||
                              mem.media?.relative_path ||
                              (item.media ? item.media.storage_key : undefined);

                            let mediaUrl: string | undefined;
                            if (mem.media?.url) {
                              mediaUrl = mem.media.url.startsWith('http')
                                ? mem.media.url
                                : getApiUrl(mem.media.url);
                            } else if (item.media?.url) {
                              mediaUrl = item.media.url;
                            } else if (storageKey) {
                              mediaUrl = getApiUrl(`/api/v1/media/${storageKey}`);
                            }

                            return (
                              <TouchableOpacity
                                key={item.memory_id || sIdx}
                                onPress={() => {
                                  const converted = convertSearchResultToMemoryItem(item);
                                  onSelectMemory(converted);
                                  onNavigate('memory_detail');
                                }}
                                style={styles.evidenceCard}
                                activeOpacity={0.85}
                              >
                                <View style={styles.evidenceCardHeader}>
                                  <View style={styles.typeBadge}>
                                    <Text style={styles.typeBadgeIcon}>
                                      {mediaType === 'audio' && '🎙️'}
                                      {mediaType === 'image' && '📸'}
                                      {mediaType === 'text' && '📝'}
                                    </Text>
                                    <Text style={styles.typeBadgeText}>
                                      {mediaType === 'audio'
                                        ? 'VOICE MEMORY'
                                        : mediaType === 'image'
                                        ? 'PHOTO EVIDENCE'
                                        : 'TEXT NOTE'}
                                    </Text>
                                  </View>
                                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                                    {item.distance_meters !== undefined && item.distance_meters !== null && (
                                      <View style={styles.distanceBadge}>
                                        <Ionicons name="location" size={11} color="#2D5A3D" />
                                        <Text style={styles.distanceBadgeText}>
                                          {item.distance_meters < 1000
                                            ? `${Math.round(item.distance_meters)}m`
                                            : `${(item.distance_meters / 1000).toFixed(1)}km`}
                                        </Text>
                                      </View>
                                    )}
                                    {item.score !== undefined && (
                                      <View style={styles.similarityBadge}>
                                        <Text style={styles.similarityText}>
                                          Match {(item.score * 100).toFixed(0)}%
                                        </Text>
                                      </View>
                                    )}
                                  </View>
                                </View>

                                {item.location ? (
                                  <View style={styles.locationTagRow}>
                                    <Ionicons name="compass-outline" size={12} color="#5E7A64" />
                                    <Text style={styles.locationTagText} numberOfLines={1}>
                                      {item.location}
                                    </Text>
                                  </View>
                                ) : null}

                                {userContext ? (
                                  <View style={styles.userContextBox}>
                                    <Ionicons
                                      name="chatbubble-ellipses-outline"
                                      size={13}
                                      color="#4A6B53"
                                    />
                                    <Text style={styles.userContextText}>
                                      <Text style={styles.userContextLabel}>Context: </Text>
                                      {userContext}
                                    </Text>
                                  </View>
                                ) : null}

                                {contentText ? (
                                  <Text style={styles.cardSnippet} numberOfLines={3}>
                                    {contentText}
                                  </Text>
                                ) : null}

                                {/* Photo Evidence Preview */}
                                {mediaType === 'image' && mediaUrl && (
                                  <View style={styles.imagePreviewContainer}>
                                    <Image source={{ uri: mediaUrl }} style={styles.cardImage} />
                                  </View>
                                )}

                                {/* Audio Waveform Preview */}
                                {mediaType === 'audio' && (
                                  <View style={styles.audioPreviewContainer}>
                                    <Ionicons name="play-circle" size={22} color="#4A6B53" />
                                    <View style={styles.audioWaveform}>
                                      {[12, 20, 16, 26, 14, 24, 18, 28, 16, 20].map((h, i) => (
                                        <View key={i} style={[styles.waveLine, { height: h }]} />
                                      ))}
                                    </View>
                                    <Text style={styles.audioPreviewText}>
                                      {originalFilename || 'Voice memo audio'}
                                    </Text>
                                  </View>
                                )}

                                {item.matched_by && item.matched_by.length > 0 && (
                                  <View style={styles.matchedTagsRow}>
                                    {item.matched_by.map((tag: string, tIdx: number) => (
                                      <View key={tIdx} style={styles.matchTag}>
                                        <Text style={styles.matchTagText}>{tag}</Text>
                                      </View>
                                    ))}
                                  </View>
                                )}

                                <View style={styles.evidenceCardFooter}>
                                  <Text style={styles.viewDetailLink}>View Full Memory →</Text>
                                </View>
                              </TouchableOpacity>
                            );
                          })}
                        </>
                      ) : (
                        /* No Relevant Memory Found */
                        <View style={styles.noMemoryCard}>
                          <View style={styles.noMemoryHeader}>
                            <Ionicons name="search" size={22} color="#8A9E8F" />
                            <Text style={styles.noMemoryTitle}>No Relevant Memory Found</Text>
                          </View>
                          <Text style={styles.noMemorySubtitle}>
                            {turn.response.answer ||
                              `I couldn't find any stored memory related to "${turn.query}".`}
                          </Text>
                        </View>
                      )}
                    </>
                  )}
                </View>
              );
            })
          )}
        </ScrollView>

        {/* Input Bar */}
        <View style={styles.inputDock}>
          <View style={styles.inputContainer}>
            <TextInput
              value={inputText}
              onChangeText={setInputText}
              onSubmitEditing={() => handleSendQuery()}
              returnKeyType="send"
              placeholder="Ask anything about your memories..."
              placeholderTextColor="#8A9E8F"
              style={styles.textInput}
              editable={!isSearching}
            />
            <TouchableOpacity
              onPress={() => handleSendQuery()}
              disabled={!inputText.trim() || isSearching}
              style={[
                styles.sendButton,
                (!inputText.trim() || isSearching) && styles.sendButtonDisabled,
              ]}
              activeOpacity={0.8}
            >
              {isSearching ? (
                <ActivityIndicator size="small" color="#FFFFFF" />
              ) : (
                <Ionicons name="arrow-up" size={20} color="#FFFFFF" />
              )}
            </TouchableOpacity>
          </View>
        </View>

        {/* Floating Bottom Navigation Dock */}
        <FloatingBottomDock activeScreenId="vault" onNavigate={onNavigate} />
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#FAF7F0',
  },
  container: {
    flex: 1,
    paddingHorizontal: 16,
    paddingTop: 10,
  },
  topHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#EBE5D8',
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
  logoGroup: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  headerTitle: {
    fontSize: 20,
    fontWeight: '800',
    color: '#1E3524',
    letterSpacing: -0.3,
  },
  headerSubtitle: {
    fontSize: 12,
    fontWeight: '600',
    color: '#5E7A64',
  },
  headerActionGroup: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  clearConvButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#EBE5D8',
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 16,
    gap: 4,
  },
  clearConvText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#5E7A64',
  },
  avatarCircle: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: '#4A6B53',
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarInitial: {
    fontSize: 14,
    fontWeight: '800',
    color: '#FFFFFF',
  },
  chatScroll: {
    flex: 1,
  },
  chatScrollContent: {
    paddingTop: 16,
    paddingBottom: 150,
  },
  emptyContainer: {
    alignItems: 'center',
    paddingTop: 30,
    paddingHorizontal: 16,
  },
  emptyIconCircle: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: '#E2ECE4',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 16,
  },
  emptyTitle: {
    fontSize: 22,
    fontWeight: '800',
    color: '#1E3524',
    marginBottom: 8,
  },
  emptySubtitle: {
    fontSize: 14,
    color: '#5E7A64',
    textAlign: 'center',
    lineHeight: 20,
    marginBottom: 28,
  },
  suggestionsBox: {
    width: '100%',
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    padding: 16,
    borderWidth: 1,
    borderColor: '#D5CDBC',
    gap: 10,
  },
  suggestionsHeader: {
    fontSize: 11,
    fontWeight: '800',
    color: '#8A9E8F',
    letterSpacing: 0.8,
    marginBottom: 4,
  },
  suggestionChip: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FAF7F0',
    paddingVertical: 12,
    paddingHorizontal: 14,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#EBE5D8',
    gap: 10,
  },
  suggestionText: {
    flex: 1,
    fontSize: 13,
    fontWeight: '600',
    color: '#1E3524',
  },
  turnBlock: {
    marginBottom: 24,
    gap: 12,
  },
  userBubbleContainer: {
    alignItems: 'flex-end',
    marginBottom: 4,
  },
  userBubble: {
    backgroundColor: '#4A6B53',
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 20,
    borderBottomRightRadius: 4,
    maxWidth: '85%',
    shadowColor: '#4A6B53',
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.2,
    shadowRadius: 6,
    elevation: 3,
  },
  userBubbleText: {
    fontSize: 15,
    fontWeight: '600',
    color: '#FFFFFF',
    lineHeight: 20,
  },
  userBubbleTime: {
    fontSize: 10,
    fontWeight: '600',
    color: '#D2E8D7',
    marginTop: 4,
    alignSelf: 'flex-end',
  },
  loadingCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    padding: 16,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: '#D5CDBC',
    gap: 14,
  },
  loadingTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: '#1E3524',
  },
  loadingSub: {
    fontSize: 12,
    color: '#5E7A64',
    marginTop: 2,
  },
  errorCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FDF2F2',
    padding: 14,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#F5C6CB',
    gap: 10,
  },
  errorText: {
    flex: 1,
    fontSize: 13,
    color: '#D9534F',
    fontWeight: '600',
  },
  answerCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    padding: 18,
    borderWidth: 1.5,
    borderColor: '#4A6B53',
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.08,
    shadowRadius: 10,
    elevation: 3,
  },
  answerHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  answerBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#4A6B53',
    paddingVertical: 4,
    paddingHorizontal: 10,
    borderRadius: 12,
    gap: 6,
  },
  answerBadgeText: {
    fontSize: 10,
    fontWeight: '800',
    color: '#FFFFFF',
    letterSpacing: 0.5,
  },
  answerBody: {
    fontSize: 15,
    color: '#1E3524',
    lineHeight: 22,
    fontWeight: '500',
    marginBottom: 12,
  },
  answerFooter: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: '#EBE5D8',
  },
  answerFooterText: {
    fontSize: 11,
    fontWeight: '600',
    color: '#5E7A64',
  },
  sourcesHeaderRow: {
    marginTop: 8,
    marginBottom: 6,
  },
  sourcesTitle: {
    fontSize: 11,
    fontWeight: '800',
    color: '#5E7A64',
    letterSpacing: 0.8,
  },
  evidenceCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 14,
    borderWidth: 1,
    borderColor: '#D5CDBC',
    gap: 8,
  },
  evidenceCardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  typeBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FAF7F0',
    paddingVertical: 3,
    paddingHorizontal: 8,
    borderRadius: 10,
    gap: 4,
  },
  typeBadgeIcon: {
    fontSize: 11,
  },
  typeBadgeText: {
    fontSize: 10,
    fontWeight: '800',
    color: '#4A6B53',
    letterSpacing: 0.4,
  },
  similarityBadge: {
    backgroundColor: '#E2ECE4',
    paddingVertical: 3,
    paddingHorizontal: 8,
    borderRadius: 10,
  },
  similarityText: {
    fontSize: 10,
    fontWeight: '700',
    color: '#4A6B53',
  },
  userContextBox: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FAF7F0',
    padding: 8,
    borderRadius: 10,
    gap: 6,
  },
  userContextText: {
    fontSize: 12,
    color: '#1E3524',
    flex: 1,
  },
  userContextLabel: {
    fontWeight: '700',
    color: '#4A6B53',
  },
  cardSnippet: {
    fontSize: 13,
    color: '#1E3524',
    lineHeight: 18,
  },
  imagePreviewContainer: {
    borderRadius: 10,
    overflow: 'hidden',
    height: 120,
    backgroundColor: '#FAF7F0',
  },
  cardImage: {
    width: '100%',
    height: '100%',
    resizeMode: 'cover',
  },
  audioPreviewContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FAF7F0',
    padding: 8,
    borderRadius: 10,
    gap: 8,
  },
  audioWaveform: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 3,
    flex: 1,
  },
  waveLine: {
    width: 3,
    backgroundColor: '#4A6B53',
    borderRadius: 2,
  },
  audioPreviewText: {
    fontSize: 11,
    color: '#5E7A64',
    fontWeight: '600',
  },
  evidenceCardFooter: {
    alignItems: 'flex-end',
    paddingTop: 4,
  },
  viewDetailLink: {
    fontSize: 12,
    fontWeight: '700',
    color: '#4A6B53',
  },
  noMemoryCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 18,
    padding: 16,
    borderWidth: 1,
    borderColor: '#D5CDBC',
    gap: 8,
  },
  noMemoryHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  noMemoryTitle: {
    fontSize: 15,
    fontWeight: '800',
    color: '#1E3524',
  },
  noMemorySubtitle: {
    fontSize: 13,
    color: '#5E7A64',
    lineHeight: 18,
  },
  inputDock: {
    position: 'absolute',
    bottom: 86,
    left: 16,
    right: 16,
  },
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderRadius: 28,
    paddingVertical: 4,
    paddingLeft: 16,
    paddingRight: 6,
    borderWidth: 1.5,
    borderColor: '#4A6B53',
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.1,
    shadowRadius: 8,
    elevation: 4,
  },
  textInput: {
    flex: 1,
    fontSize: 14,
    color: '#1E3524',
    paddingVertical: 10,
  },
  sendButton: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: '#4A6B53',
    alignItems: 'center',
    justifyContent: 'center',
  },
  sendButtonDisabled: {
    backgroundColor: '#C5D6C9',
  },
  groupFilterBar: {
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#E5DFD5',
    backgroundColor: '#FAF7F0',
  },
  groupFilterScroll: {
    paddingHorizontal: 16,
    gap: 8,
  },
  groupFilterChip: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 14,
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#D5CDBC',
    gap: 5,
  },
  groupFilterChipActive: {
    backgroundColor: '#4A6B53',
    borderColor: '#4A6B53',
  },
  groupFilterText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#5E7A64',
  },
  groupFilterTextActive: {
    color: '#FFFFFF',
  },
  radiusControlContainer: {
    backgroundColor: '#FAF7F0',
    borderBottomWidth: 1,
    borderBottomColor: '#E5DFD5',
    paddingHorizontal: 16,
    paddingVertical: 10,
    gap: 8,
  },
  radiusHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  radiusTitleGroup: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    flex: 1,
  },
  radiusTitleText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#1E3524',
  },
  reSearchBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: '#2D5A3D',
    paddingVertical: 4,
    paddingHorizontal: 9,
    borderRadius: 8,
  },
  reSearchBtnText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  customLocationApplyBtn: {
    backgroundColor: '#4A6B53',
    paddingVertical: 4,
    paddingHorizontal: 8,
    borderRadius: 6,
  },
  customLocationApplyText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  radiusToggleBtn: {
    paddingVertical: 4,
    paddingHorizontal: 8,
    borderRadius: 8,
    backgroundColor: '#EDE7DC',
  },
  radiusToggleBtnActive: {
    backgroundColor: '#E2EFE5',
  },
  radiusToggleText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#5E7A64',
  },
  radiusToggleTextActive: {
    color: '#2D5A3D',
  },
  radiusPillsRow: {
    flexDirection: 'row',
    gap: 8,
    alignItems: 'center',
  },
  radiusPill: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 14,
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#D5CDBC',
  },
  radiusPillActive: {
    backgroundColor: '#4A6B53',
    borderColor: '#4A6B53',
  },
  radiusPillText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#5E7A64',
  },
  radiusPillTextActive: {
    color: '#FFFFFF',
  },
  activeRadiusSection: {
    marginTop: 4,
    padding: 10,
    borderRadius: 12,
    backgroundColor: '#F3EFE6',
    borderWidth: 1,
    borderColor: '#DFD8C8',
    gap: 8,
  },
  stepperRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  stepBtn: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#D5CDBC',
    alignItems: 'center',
    justifyContent: 'center',
  },
  stepBtnDisabled: {
    opacity: 0.35,
  },
  sliderTrackContainer: {
    flex: 1,
    gap: 4,
  },
  sliderTrackBackground: {
    height: 8,
    borderRadius: 4,
    backgroundColor: '#DCD4C4',
    overflow: 'hidden',
  },
  sliderTrackFill: {
    height: '100%',
    borderRadius: 4,
    backgroundColor: '#4A6B53',
  },
  sliderValueText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#2D5A3D',
    textAlign: 'center',
  },
  placeChipsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 6,
  },
  placeChipsLabel: {
    fontSize: 11,
    fontWeight: '600',
    color: '#5E7A64',
  },
  placeChip: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 8,
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#D5CDBC',
  },
  placeChipActive: {
    backgroundColor: '#2D5A3D',
    borderColor: '#2D5A3D',
  },
  placeChipText: {
    fontSize: 11,
    fontWeight: '600',
    color: '#4A6B53',
  },
  placeChipTextActive: {
    color: '#FFFFFF',
  },
  customLocationInputBox: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#D5CDBC',
    paddingHorizontal: 8,
    gap: 6,
  },
  customLocationInput: {
    flex: 1,
    paddingVertical: 6,
    fontSize: 12,
    color: '#1E3524',
  },
  turnRadiusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginTop: 4,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 6,
    backgroundColor: '#E2EFE5',
    alignSelf: 'flex-start',
  },
  turnRadiusBadgeText: {
    fontSize: 10,
    fontWeight: '700',
    color: '#2D5A3D',
  },
  locationTagRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginTop: 4,
  },
  locationTagText: {
    fontSize: 11,
    color: '#5E7A64',
    fontWeight: '500',
  },
  distanceBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 3,
    backgroundColor: '#E2EFE5',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 10,
  },
  distanceBadgeText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#2D5A3D',
  },
  matchedTagsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 4,
    marginTop: 6,
  },
  matchTag: {
    backgroundColor: '#EFEAE1',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 6,
  },
  matchTagText: {
    fontSize: 10,
    color: '#5E7A64',
    fontWeight: '500',
  },
});
