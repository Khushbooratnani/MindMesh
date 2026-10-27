import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  ScrollView,
  Image,
  StyleSheet,
  SafeAreaView,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { createAudioPlayer, AudioPlayer } from 'expo-audio';
import { MemoryItem, ScreenId } from '../types';

interface MemoryDetailProps {
  memory: MemoryItem | null;
  onNavigate: (id: ScreenId) => void;
}

export const MemoryDetailScreen: React.FC<MemoryDetailProps> = ({
  memory,
  onNavigate,
}) => {
  const [player, setPlayer] = useState<AudioPlayer | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);

  useEffect(() => {
    return () => {
      if (player) {
        player.remove();
      }
    };
  }, [player]);

  const handleToggleAudio = () => {
    if (!memory?.audioUri) return;

    if (player) {
      if (isPlaying) {
        player.pause();
        setIsPlaying(false);
      } else {
        player.play();
        setIsPlaying(true);
      }
    } else {
      try {
        const newPlayer = createAudioPlayer(memory.audioUri);
        setPlayer(newPlayer);
        newPlayer.play();
        setIsPlaying(true);
        newPlayer.addListener('playbackStatusUpdate', (status) => {
          if (status.didJustFinish) {
            setIsPlaying(false);
          }
        });
      } catch (err) {
        console.error('Audio playback error:', err);
      }
    }
  };

  if (!memory) {
    return (
      <SafeAreaView style={styles.safeArea}>
        <View style={styles.errorContainer}>
          <Text style={styles.errorText}>No memory selected</Text>
          <TouchableOpacity
            style={styles.backButton}
            onPress={() => onNavigate('home')}
          >
            <Text style={styles.backButtonText}>Return to Home Stream</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  const rawV1 = memory.rawMemoryV1;
  const userContext = rawV1?.user_context || rawV1?.content?.user_context;
  const sentiment = rawV1?.semantics?.sentiment || memory.sentiment;

  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.container}>
        {/* Top Header */}
        <View style={styles.topHeader}>
          <TouchableOpacity
            style={styles.backPill}
            onPress={() => onNavigate('home')}
            activeOpacity={0.8}
          >
            <Ionicons name="arrow-back" size={16} color="#4A6B53" />
            <Text style={styles.backPillText}>Feed</Text>
          </TouchableOpacity>

          <View style={styles.headerRight}>
            <View style={styles.phase1Badge}>
              <Text style={styles.phase1BadgeText}>
                {rawV1 ? 'Phase 1 MemoryV1' : 'Local Archive'}
              </Text>
            </View>
          </View>
        </View>

        {/* Scrollable Content */}
        <ScrollView style={styles.scrollContent} showsVerticalScrollIndicator={false}>
          {/* Title & Metadata */}
          <View style={styles.titleSection}>
            <View style={styles.badgeRow}>
              <View style={styles.modalityBadge}>
                <Text style={styles.modalityBadgeText}>{memory.type.toUpperCase()}</Text>
              </View>
              <Text style={styles.dateText}>{memory.dateStr}</Text>

              {sentiment && (
                <View
                  style={[
                    styles.sentimentBadge,
                    sentiment === 'positive'
                      ? styles.sentimentPositive
                      : sentiment === 'negative'
                      ? styles.sentimentNegative
                      : styles.sentimentNeutral,
                  ]}
                >
                  <Text style={styles.sentimentText}>Sentiment: {sentiment}</Text>
                </View>
              )}
            </View>

            <Text style={styles.mainTitle}>
              {rawV1?.content?.summary || memory.title}
            </Text>

            {memory.location && (
              <View style={styles.locationRow}>
                <Ionicons name="location" size={14} color="#4A6B53" />
                <Text style={styles.locationText}>{memory.location}</Text>
              </View>
            )}
          </View>

          {/* Original Image Preview */}
          {memory.imageUri && (
            <View style={styles.mediaCard}>
              <Image source={{ uri: memory.imageUri }} style={styles.mediaImage} />
              {rawV1?.media && (
                <View style={styles.mediaFileInfo}>
                  <Text style={styles.mediaFileName}>{rawV1.media.original_filename}</Text>
                  <Text style={styles.mediaFileSize}>
                    {(rawV1.media.size_bytes / 1024).toFixed(0)} KB
                  </Text>
                </View>
              )}
            </View>
          )}

          {/* Audio Player if Voice Memo */}
          {memory.type === 'voice' && (
            <View style={styles.audioPlayerCard}>
              <TouchableOpacity
                style={styles.playButton}
                onPress={handleToggleAudio}
                activeOpacity={0.8}
              >
                <Ionicons
                  name={isPlaying ? 'pause' : 'play'}
                  size={20}
                  color="#FFFFFF"
                />
              </TouchableOpacity>

              <View style={styles.audioWaveform}>
                {[10, 20, 32, 14, 28, 22, 12, 26, 18, 30, 16, 24, 14].map((h, i) => (
                  <View
                    key={i}
                    style={[styles.audioWaveBar, { height: h }]}
                  />
                ))}
              </View>

              <Text style={styles.audioTimeText}>
                {isPlaying ? 'Playing' : 'Voice Memo'}
              </Text>
            </View>
          )}

          {/* User Provided Context (Clearly Separated) */}
          {userContext && (
            <View style={styles.contextCard}>
              <View style={styles.sectionHeaderRow}>
                <Ionicons name="chatbubble-ellipses-outline" size={14} color="#4A6B53" />
                <Text style={styles.contextCardLabel}>User Provided Context</Text>
              </View>
              <Text style={styles.contextCardText}>"{userContext}"</Text>
            </View>
          )}

          {/* AI Extracted Structured Content */}
          <View style={styles.contentCard}>
            <Text style={styles.cardHeaderTitle}>
              {memory.type === 'voice'
                ? 'Transcribed & Structured Content'
                : 'Extracted Memory Description'}
            </Text>
            <Text style={styles.contentText}>
              {rawV1?.content?.description || memory.fullContent || memory.snippet}
            </Text>
          </View>

          {/* Cognitive Entities Chips (People, Places, Events, Orgs) */}
          {((rawV1?.entities &&
            (rawV1.entities.people.length > 0 ||
              rawV1.entities.places.length > 0 ||
              rawV1.entities.events.length > 0)) ||
            (memory.entities && memory.entities.length > 0)) && (
            <View style={styles.entitiesCard}>
              <View style={styles.sectionHeaderRow}>
                <Ionicons name="sparkles" size={14} color="#4A6B53" />
                <Text style={styles.entitiesCardTitle}>Extracted Cognitive Entities</Text>
              </View>

              <View style={styles.chipsContainer}>
                {rawV1 ? (
                  <>
                    {rawV1.entities.people.map((p, i) => (
                      <View key={`p-${i}`} style={styles.entityChipPerson}>
                        <Text style={styles.chipTypePerson}>person: </Text>
                        <Text style={styles.chipVal}>{p}</Text>
                      </View>
                    ))}
                    {Array.from(
                      new Set([...rawV1.entities.places, ...rawV1.entities.locations])
                    ).map((loc, i) => (
                      <View key={`l-${i}`} style={styles.entityChipPlace}>
                        <Text style={styles.chipTypePlace}>place: </Text>
                        <Text style={styles.chipVal}>{loc}</Text>
                      </View>
                    ))}
                    {rawV1.entities.events.map((ev, i) => (
                      <View key={`e-${i}`} style={styles.entityChipEvent}>
                        <Text style={styles.chipTypeEvent}>event: </Text>
                        <Text style={styles.chipVal}>{ev}</Text>
                      </View>
                    ))}
                    {rawV1.entities.organizations.map((org, i) => (
                      <View key={`o-${i}`} style={styles.entityChipOrg}>
                        <Text style={styles.chipTypeOrg}>org: </Text>
                        <Text style={styles.chipVal}>{org}</Text>
                      </View>
                    ))}
                  </>
                ) : (
                  memory.entities?.map((ent, idx) => (
                    <View key={idx} style={styles.entityChipPlace}>
                      <Text style={styles.chipTypePlace}>{ent.type}: </Text>
                      <Text style={styles.chipVal}>{ent.name}</Text>
                    </View>
                  ))
                )}
              </View>
            </View>
          )}

          {/* Topics & Activities */}
          {rawV1 &&
            (rawV1.semantics.topics.length > 0 ||
              rawV1.semantics.activities.length > 0 ||
              rawV1.semantics.mood.length > 0) && (
              <View style={styles.semanticsCard}>
                <Text style={styles.cardHeaderTitle}>Topics & Activities</Text>
                <View style={styles.chipsContainer}>
                  {rawV1.semantics.topics.map((t, idx) => (
                    <View key={`top-${idx}`} style={styles.topicChip}>
                      <Text style={styles.topicChipText}>#{t}</Text>
                    </View>
                  ))}
                  {rawV1.semantics.activities.map((a, idx) => (
                    <View key={`act-${idx}`} style={styles.activityChip}>
                      <Text style={styles.activityChipText}>⚡ {a}</Text>
                    </View>
                  ))}
                  {rawV1.semantics.mood.map((m, idx) => (
                    <View key={`mood-${idx}`} style={styles.moodChip}>
                      <Text style={styles.moodChipText}>😊 {m}</Text>
                    </View>
                  ))}
                </View>
              </View>
            )}

          {/* Temporal Data */}
          {rawV1 &&
            (rawV1.temporal.mentioned_dates.length > 0 ||
              rawV1.temporal.inferred_time ||
              rawV1.temporal.time_of_day) && (
              <View style={styles.temporalCard}>
                <Text style={styles.cardHeaderTitle}>Temporal Information</Text>
                <View style={styles.temporalRow}>
                  {rawV1.temporal.mentioned_dates.length > 0 && (
                    <Text style={styles.temporalText}>
                      📅 Dates: <Text style={styles.temporalBold}>{rawV1.temporal.mentioned_dates.join(', ')}</Text>
                    </Text>
                  )}
                  {rawV1.temporal.inferred_time && (
                    <Text style={styles.temporalText}>
                      ⏰ Inferred: <Text style={styles.temporalBold}>{rawV1.temporal.inferred_time}</Text>
                    </Text>
                  )}
                  {rawV1.temporal.time_of_day && rawV1.temporal.time_of_day !== 'unknown' && (
                    <Text style={styles.temporalText}>
                      ☀️ Time of Day: <Text style={styles.temporalBold}>{rawV1.temporal.time_of_day}</Text>
                    </Text>
                  )}
                </View>
              </View>
            )}

          {/* Model Processing Metadata */}
          {rawV1 && (
            <View style={styles.metadataCard}>
              <Text style={styles.metadataText}>Model: {rawV1.processing.llm_model}</Text>
              <Text style={styles.metadataStatus}>Status: {rawV1.processing.status.toUpperCase()}</Text>
            </View>
          )}

          {/* Return Button */}
          <TouchableOpacity
            style={styles.returnButton}
            onPress={() => onNavigate('home')}
            activeOpacity={0.88}
          >
            <Text style={styles.returnButtonText}>Return to Memory Feed</Text>
          </TouchableOpacity>
        </ScrollView>
      </View>
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
    paddingTop: 8,
  },
  errorContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
    gap: 16,
  },
  errorText: {
    fontSize: 16,
    fontWeight: '700',
    color: '#233529',
  },
  backButton: {
    backgroundColor: '#4A6B53',
    paddingVertical: 12,
    paddingHorizontal: 20,
    borderRadius: 14,
  },
  backButtonText: {
    color: '#FFFFFF',
    fontWeight: '700',
  },
  topHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#E5DFD5',
  },
  backPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: '#FFFFFF',
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#D5CDBC',
  },
  backPillText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#4A6B53',
  },
  headerRight: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  phase1Badge: {
    backgroundColor: '#EFEAE1',
    paddingVertical: 4,
    paddingHorizontal: 10,
    borderRadius: 12,
  },
  phase1BadgeText: {
    fontSize: 10,
    fontWeight: '800',
    color: '#4A6B53',
  },
  scrollContent: {
    flex: 1,
    marginTop: 10,
  },
  titleSection: {
    gap: 8,
    marginBottom: 14,
  },
  badgeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 8,
  },
  modalityBadge: {
    backgroundColor: '#4A6B53',
    paddingVertical: 3,
    paddingHorizontal: 8,
    borderRadius: 6,
  },
  modalityBadgeText: {
    color: '#FFFFFF',
    fontSize: 10,
    fontWeight: '800',
  },
  dateText: {
    fontSize: 11,
    color: '#5E7A64',
    fontWeight: '500',
  },
  sentimentBadge: {
    paddingVertical: 3,
    paddingHorizontal: 8,
    borderRadius: 10,
  },
  sentimentPositive: {
    backgroundColor: '#DCFCE7',
  },
  sentimentNegative: {
    backgroundColor: '#FEE2E2',
  },
  sentimentNeutral: {
    backgroundColor: '#F3F4F6',
  },
  sentimentText: {
    fontSize: 10,
    fontWeight: '700',
    color: '#233529',
    textTransform: 'uppercase',
  },
  mainTitle: {
    fontSize: 19,
    fontWeight: '800',
    color: '#233529',
    lineHeight: 25,
  },
  locationRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  locationText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#4A6B53',
  },
  mediaCard: {
    borderRadius: 18,
    overflow: 'hidden',
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#D5CDBC',
    marginBottom: 14,
  },
  mediaImage: {
    width: '100%',
    height: 220,
    resizeMode: 'cover',
  },
  mediaFileInfo: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    padding: 8,
    backgroundColor: '#FAF7F0',
  },
  mediaFileName: {
    fontSize: 10,
    color: '#5E7A64',
    fontFamily: 'System',
  },
  mediaFileSize: {
    fontSize: 10,
    color: '#5E7A64',
    fontFamily: 'System',
  },
  audioPlayerCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    padding: 12,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#D5CDBC',
    marginBottom: 14,
    gap: 12,
  },
  playButton: {
    width: 40,
    height: 40,
    borderRadius: 12,
    backgroundColor: '#4A6B53',
    alignItems: 'center',
    justifyContent: 'center',
  },
  audioWaveform: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 3,
    height: 32,
  },
  audioWaveBar: {
    width: 3,
    backgroundColor: '#4A6B53',
    borderRadius: 2,
  },
  audioTimeText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#5E7A64',
  },
  contextCard: {
    backgroundColor: '#F0ECE1',
    borderRadius: 16,
    padding: 14,
    borderWidth: 1,
    borderColor: '#D5CDBC',
    marginBottom: 14,
    gap: 4,
  },
  sectionHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  contextCardLabel: {
    fontSize: 10,
    fontWeight: '800',
    color: '#4A6B53',
    textTransform: 'uppercase',
    letterSpacing: 0.8,
  },
  contextCardText: {
    fontSize: 12,
    fontStyle: 'italic',
    color: '#233529',
    lineHeight: 18,
  },
  contentCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
    borderColor: '#E5DFD5',
    marginBottom: 14,
    gap: 6,
  },
  cardHeaderTitle: {
    fontSize: 11,
    fontWeight: '800',
    color: '#5E7A64',
    textTransform: 'uppercase',
    letterSpacing: 0.8,
  },
  contentText: {
    fontSize: 13,
    color: '#233529',
    lineHeight: 20,
  },
  entitiesCard: {
    backgroundColor: '#FAF7F0',
    borderRadius: 16,
    padding: 14,
    borderWidth: 1,
    borderColor: '#D5CDBC',
    marginBottom: 14,
    gap: 10,
  },
  entitiesCardTitle: {
    fontSize: 11,
    fontWeight: '800',
    color: '#4A6B53',
    textTransform: 'uppercase',
    letterSpacing: 0.8,
  },
  chipsContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
  },
  entityChipPerson: {
    flexDirection: 'row',
    backgroundColor: '#FFFFFF',
    paddingVertical: 4,
    paddingHorizontal: 8,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#BFDBFE',
  },
  chipTypePerson: {
    fontSize: 10,
    color: '#2563EB',
    fontWeight: '700',
  },
  entityChipPlace: {
    flexDirection: 'row',
    backgroundColor: '#FFFFFF',
    paddingVertical: 4,
    paddingHorizontal: 8,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#A7F3D0',
  },
  chipTypePlace: {
    fontSize: 10,
    color: '#059669',
    fontWeight: '700',
  },
  entityChipEvent: {
    flexDirection: 'row',
    backgroundColor: '#FFFFFF',
    paddingVertical: 4,
    paddingHorizontal: 8,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#FDE68A',
  },
  chipTypeEvent: {
    fontSize: 10,
    color: '#D97706',
    fontWeight: '700',
  },
  entityChipOrg: {
    flexDirection: 'row',
    backgroundColor: '#FFFFFF',
    paddingVertical: 4,
    paddingHorizontal: 8,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#E9D5FF',
  },
  chipTypeOrg: {
    fontSize: 10,
    color: '#7C3AED',
    fontWeight: '700',
  },
  chipVal: {
    fontSize: 10,
    fontWeight: '700',
    color: '#233529',
  },
  semanticsCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 14,
    borderWidth: 1,
    borderColor: '#E5DFD5',
    marginBottom: 14,
    gap: 8,
  },
  topicChip: {
    backgroundColor: '#FAF7F0',
    paddingVertical: 3,
    paddingHorizontal: 8,
    borderRadius: 6,
  },
  topicChipText: {
    fontSize: 10,
    fontWeight: '700',
    color: '#4A6B53',
  },
  activityChip: {
    backgroundColor: '#F3F4F6',
    paddingVertical: 3,
    paddingHorizontal: 8,
    borderRadius: 6,
  },
  activityChipText: {
    fontSize: 10,
    fontWeight: '600',
    color: '#374151',
  },
  moodChip: {
    backgroundColor: '#FEF3C7',
    paddingVertical: 3,
    paddingHorizontal: 8,
    borderRadius: 6,
  },
  moodChipText: {
    fontSize: 10,
    fontWeight: '600',
    color: '#92400E',
  },
  temporalCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 14,
    borderWidth: 1,
    borderColor: '#E5DFD5',
    marginBottom: 14,
    gap: 6,
  },
  temporalRow: {
    gap: 4,
  },
  temporalText: {
    fontSize: 11,
    color: '#5E7A64',
  },
  temporalBold: {
    color: '#233529',
    fontWeight: '700',
  },
  metadataCard: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    backgroundColor: '#FAF7F0',
    padding: 10,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#E5DFD5',
    marginBottom: 14,
  },
  metadataText: {
    fontSize: 9,
    fontFamily: 'System',
    color: '#5E7A64',
  },
  metadataStatus: {
    fontSize: 9,
    fontFamily: 'System',
    color: '#16A34A',
    fontWeight: '700',
  },
  returnButton: {
    backgroundColor: '#4A6B53',
    paddingVertical: 14,
    borderRadius: 16,
    alignItems: 'center',
    marginBottom: 24,
  },
  returnButtonText: {
    color: '#FFFFFF',
    fontSize: 13,
    fontWeight: '700',
  },
});
