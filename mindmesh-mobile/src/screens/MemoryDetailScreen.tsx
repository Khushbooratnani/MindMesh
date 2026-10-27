import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  ScrollView,
  Image,
  StyleSheet,
  TextInput,
  Modal,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { createAudioPlayer, AudioPlayer } from 'expo-audio';
import { MemoryItem, ScreenId, CommentItem, Group, MemorySharesResponse } from '../types';
import {
  getComments,
  addComment,
  deleteComment,
  getGroups,
  shareMemory,
  revokeMemoryShare,
  getMemoryShares,
} from '../services/apiClient';
import { useAuth } from '../auth/AuthContext';

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

  const { user } = useAuth();
  const [comments, setComments] = useState<CommentItem[]>([]);
  const [loadingComments, setLoadingComments] = useState(false);
  const [commentText, setCommentText] = useState('');
  const [submittingComment, setSubmittingComment] = useState(false);
  const [shareModalVisible, setShareModalVisible] = useState(false);
  const [groups, setGroups] = useState<Group[]>([]);
  const [shares, setShares] = useState<MemorySharesResponse | null>(null);

  const memoryId = memory?.rawMemoryV1?.memory_id || memory?.id;
  const isPrivateLocker =
    memory?.privacy === 'encrypted' ||
    memory?.rawMemoryV1?.system?.privacy === 'PRIVATE_LOCKER';

  const loadCommentsAndShares = async () => {
    if (!memoryId) return;
    try {
      setLoadingComments(true);
      const [commentList, shareData, groupList] = await Promise.all([
        getComments(memoryId).catch(() => []),
        getMemoryShares(memoryId).catch(() => null),
        getGroups().catch(() => []),
      ]);
      setComments(commentList);
      setShares(shareData);
      setGroups(groupList);
    } catch {
      // ignore
    } finally {
      setLoadingComments(false);
    }
  };

  useEffect(() => {
    if (memoryId && !isPrivateLocker) {
      loadCommentsAndShares();
    }
  }, [memoryId, isPrivateLocker]);

  const handleAddComment = async () => {
    if (!commentText.trim() || !memoryId) return;
    setSubmittingComment(true);
    try {
      const newComment = await addComment(memoryId, commentText.trim());
      setComments((prev) => [...prev, newComment]);
      setCommentText('');
    } catch (err: any) {
      Alert.alert('Error', err?.message || 'Failed to add comment');
    } finally {
      setSubmittingComment(false);
    }
  };

  const handleDeleteComment = async (commentId: string) => {
    try {
      await deleteComment(commentId);
      setComments((prev) => prev.filter((c) => c.id !== commentId));
    } catch (err: any) {
      Alert.alert('Error', err?.message || 'Failed to delete comment');
    }
  };

  const handleShareToGroup = async (groupId: string) => {
    if (!memoryId) return;
    try {
      await shareMemory(memoryId, [groupId]);
      Alert.alert('Success', 'Memory shared to group');
      loadCommentsAndShares();
    } catch (err: any) {
      Alert.alert('Error', err?.message || 'Failed to share memory');
    }
  };

  const handleRevokeShare = async (groupId: string) => {
    if (!memoryId) return;
    try {
      await revokeMemoryShare(memoryId, groupId);
      Alert.alert('Success', 'Sharing revoked');
      loadCommentsAndShares();
    } catch (err: any) {
      Alert.alert('Error', err?.message || 'Failed to revoke sharing');
    }
  };

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

          {/* Collaborative Sharing & Permissions */}
          {!isPrivateLocker ? (
            <View style={styles.shareSection}>
              <View style={styles.shareHeaderRow}>
                <Text style={styles.sectionHeading}>Collaborative Sharing</Text>
                <TouchableOpacity
                  style={styles.openShareBtn}
                  onPress={() => setShareModalVisible(true)}
                >
                  <Ionicons name="share-social-outline" size={15} color="#4A6B53" />
                  <Text style={styles.openShareBtnText}>Share to Group</Text>
                </TouchableOpacity>
              </View>

              {shares && shares.group_shares.length > 0 && (
                <View style={styles.sharedGroupsRow}>
                  <Text style={styles.sharedLabel}>Shared with {shares.group_shares.length} group(s):</Text>
                  {shares.group_shares.map((gs) => {
                    const grp = groups.find((g) => g.id === gs.group_id);
                    return (
                      <View key={gs.id} style={styles.groupShareChip}>
                        <Text style={styles.groupShareChipText}>{grp?.name || 'Group'}</Text>
                        <TouchableOpacity onPress={() => handleRevokeShare(gs.group_id)}>
                          <Ionicons name="close-circle" size={16} color="#D9534F" />
                        </TouchableOpacity>
                      </View>
                    );
                  })}
                </View>
              )}
            </View>
          ) : (
            <View style={styles.lockerIsolationNotice}>
              <Ionicons name="lock-closed" size={16} color="#B25E09" />
              <Text style={styles.lockerIsolationText}>
                Private Locker memory: Hard isolation active. Sharing and comments are disabled.
              </Text>
            </View>
          )}

          {/* Collaborative Discussion & Knowledge Comments */}
          {!isPrivateLocker && (
            <View style={styles.commentsSection}>
              <Text style={styles.sectionHeading}>
                Collaborative Discussion ({comments.length})
              </Text>

              {/* Add comment row */}
              <View style={styles.commentInputRow}>
                <TextInput
                  style={styles.commentInput}
                  placeholder="Add insight, note, or fact..."
                  placeholderTextColor="#8B9E90"
                  value={commentText}
                  onChangeText={setCommentText}
                />
                <TouchableOpacity
                  style={styles.commentSubmitBtn}
                  onPress={handleAddComment}
                  disabled={submittingComment || !commentText.trim()}
                >
                  {submittingComment ? (
                    <ActivityIndicator size="small" color="#FFFFFF" />
                  ) : (
                    <Ionicons name="send" size={16} color="#FFFFFF" />
                  )}
                </TouchableOpacity>
              </View>

              {/* Comments list */}
              {comments.map((c) => (
                <View key={c.id} style={styles.commentItem}>
                  <View style={styles.commentTopRow}>
                    <Text style={styles.commentAuthor}>{c.author_username}</Text>
                    <View style={styles.commentMetaRight}>
                      {c.is_knowledge_eligible && (
                        <View style={styles.knowledgeEligibleBadge}>
                          <Text style={styles.knowledgeEligibleText}>KNOWLEDGE</Text>
                        </View>
                      )}
                      {user && c.author_id === user.id && (
                        <TouchableOpacity onPress={() => handleDeleteComment(c.id)}>
                          <Ionicons name="trash-outline" size={14} color="#D9534F" />
                        </TouchableOpacity>
                      )}
                    </View>
                  </View>
                  <Text style={styles.commentContent}>{c.content}</Text>
                </View>
              ))}
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

      {/* Share to Group Modal */}
      <Modal visible={shareModalVisible} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Share Memory to Group</Text>
              <TouchableOpacity onPress={() => setShareModalVisible(false)}>
                <Ionicons name="close" size={22} color="#1F2923" />
              </TouchableOpacity>
            </View>

            {groups.length === 0 ? (
              <Text style={styles.emptyGroupsText}>
                No groups found. Create a group first from the Groups tab.
              </Text>
            ) : (
              groups.map((g) => {
                const isAlreadyShared = shares?.group_shares.some((gs) => gs.group_id === g.id);
                return (
                  <View key={g.id} style={styles.groupOptionRow}>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.groupOptionName}>{g.name}</Text>
                      <Text style={styles.groupOptionRole}>Role: {g.my_role}</Text>
                    </View>
                    {isAlreadyShared ? (
                      <TouchableOpacity
                        style={styles.revokeShareBtn}
                        onPress={() => handleRevokeShare(g.id)}
                      >
                        <Text style={styles.revokeShareBtnText}>Revoke</Text>
                      </TouchableOpacity>
                    ) : (
                      <TouchableOpacity
                        style={styles.grantShareBtn}
                        onPress={() => handleShareToGroup(g.id)}
                      >
                        <Text style={styles.grantShareBtnText}>Share</Text>
                      </TouchableOpacity>
                    )}
                  </View>
                );
              })
            )}

            <TouchableOpacity
              style={styles.doneBtn}
              onPress={() => setShareModalVisible(false)}
            >
              <Text style={styles.doneBtnText}>Done</Text>
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
  shareSection: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 14,
    borderWidth: 1,
    borderColor: '#E5DFD5',
    marginBottom: 14,
  },
  shareHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  sectionHeading: {
    fontSize: 14,
    fontWeight: '800',
    color: '#1F2923',
  },
  openShareBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FAF7F0',
    borderWidth: 1,
    borderColor: '#D5CDBC',
    paddingVertical: 5,
    paddingHorizontal: 10,
    borderRadius: 12,
    gap: 4,
  },
  openShareBtnText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#4A6B53',
  },
  sharedGroupsRow: {
    marginTop: 10,
    gap: 6,
  },
  sharedLabel: {
    fontSize: 11,
    color: '#5E7A64',
    fontWeight: '600',
  },
  groupShareChip: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: '#FAF7F0',
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#E2DDD2',
  },
  groupShareChipText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#1F2923',
  },
  lockerIsolationNotice: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FEF3C7',
    padding: 12,
    borderRadius: 12,
    marginBottom: 14,
    gap: 8,
  },
  lockerIsolationText: {
    flex: 1,
    fontSize: 11,
    color: '#92400E',
    fontWeight: '600',
  },
  commentsSection: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 14,
    borderWidth: 1,
    borderColor: '#E5DFD5',
    marginBottom: 14,
  },
  commentInputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 10,
    marginBottom: 12,
    gap: 8,
  },
  commentInput: {
    flex: 1,
    backgroundColor: '#FAF7F0',
    borderWidth: 1,
    borderColor: '#D5CDBC',
    borderRadius: 12,
    paddingHorizontal: 12,
    paddingVertical: 8,
    fontSize: 13,
    color: '#1F2923',
  },
  commentSubmitBtn: {
    backgroundColor: '#4A6B53',
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
  },
  commentItem: {
    backgroundColor: '#FAF7F0',
    borderRadius: 10,
    padding: 10,
    marginBottom: 8,
  },
  commentTopRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
  },
  commentAuthor: {
    fontSize: 12,
    fontWeight: '700',
    color: '#1F2923',
  },
  commentMetaRight: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  knowledgeEligibleBadge: {
    backgroundColor: '#EAF2EC',
    paddingVertical: 2,
    paddingHorizontal: 6,
    borderRadius: 4,
  },
  knowledgeEligibleText: {
    fontSize: 8,
    fontWeight: '800',
    color: '#2D4A36',
    letterSpacing: 0.5,
  },
  commentContent: {
    fontSize: 13,
    color: '#2D4A36',
    lineHeight: 18,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.45)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: '#FFFFFF',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    padding: 20,
    paddingBottom: 40,
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  modalTitle: {
    fontSize: 16,
    fontWeight: '800',
    color: '#1F2923',
  },
  emptyGroupsText: {
    fontSize: 13,
    color: '#5E7A64',
    textAlign: 'center',
    marginVertical: 20,
  },
  groupOptionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#F0ECE4',
  },
  groupOptionName: {
    fontSize: 14,
    fontWeight: '700',
    color: '#1F2923',
  },
  groupOptionRole: {
    fontSize: 11,
    color: '#8B9E90',
  },
  grantShareBtn: {
    backgroundColor: '#4A6B53',
    paddingVertical: 6,
    paddingHorizontal: 14,
    borderRadius: 14,
  },
  grantShareBtnText: {
    color: '#FFFFFF',
    fontSize: 11,
    fontWeight: '700',
  },
  revokeShareBtn: {
    borderWidth: 1,
    borderColor: '#D9534F',
    paddingVertical: 5,
    paddingHorizontal: 12,
    borderRadius: 14,
  },
  revokeShareBtnText: {
    color: '#D9534F',
    fontSize: 11,
    fontWeight: '700',
  },
  doneBtn: {
    marginTop: 16,
    backgroundColor: '#FAF7F0',
    borderWidth: 1,
    borderColor: '#D5CDBC',
    paddingVertical: 12,
    borderRadius: 16,
    alignItems: 'center',
  },
  doneBtnText: {
    fontSize: 13,
    fontWeight: '700',
    color: '#4A6B53',
  },
});
