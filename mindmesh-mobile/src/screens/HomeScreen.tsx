import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  Image,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
  Modal,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { MindMeshLogo } from '../components/MindMeshLogo';
import { FloatingBottomDock } from '../components/FloatingBottomDock';
import { MemoryItem, ScreenId } from '../types';
import { useAuth } from '../auth/AuthContext';

interface HomeProps {
  memories: MemoryItem[];
  totalCount?: number;
  isLoadingFeed?: boolean;
  onRefreshFeed?: () => void;
  onNavigate: (id: ScreenId) => void;
  onSelectMemory: (memory: MemoryItem) => void;
}

export const HomeScreen: React.FC<HomeProps> = ({
  memories,
  totalCount,
  isLoadingFeed = false,
  onRefreshFeed,
  onNavigate,
  onSelectMemory,
}) => {
  const { user, signOut } = useAuth();
  const [activeFilter, setActiveFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [isProfileModalOpen, setIsProfileModalOpen] = useState(false);

  const filterTabs = [
    { id: 'all', label: 'All Items', icon: 'apps' },
    { id: 'voice', label: '🎙️ Voice', icon: 'mic' },
    { id: 'photo', label: '📸 Photos', icon: 'image' },
    { id: 'note', label: '📝 Notes', icon: 'document-text' },
  ];

  const handleClearSearch = () => {
    setSearchQuery('');
  };

  // Local feed filtering across title, content, snippet, transcript, tags, location, entities
  const filteredMemories = memories.filter((m) => {
    // P0 PRIVACY ISOLATION: Main Stream feed must NEVER render Private Locker memories
    if (m.privacy === 'encrypted' || m.isEncrypted || m.rawMemoryV1?.system?.privacy === 'PRIVATE_LOCKER') {
      return false;
    }

    if (activeFilter !== 'all' && m.type !== activeFilter) return false;

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      const matchTitle = m.title?.toLowerCase().includes(q);
      const matchSnippet = m.snippet?.toLowerCase().includes(q);
      const matchFullContent = m.fullContent?.toLowerCase().includes(q);
      const matchTranscript = m.transcript?.toLowerCase().includes(q);
      const matchLocation = m.location?.toLowerCase().includes(q);
      const matchTags = m.tags?.some((t) => t.toLowerCase().includes(q));
      const matchEntities = m.entities?.some((e) => e.name.toLowerCase().includes(q));
      const matchCleanText = m.rawMemoryV1?.content?.clean_text?.toLowerCase().includes(q);
      const matchSummary = m.rawMemoryV1?.content?.summary?.toLowerCase().includes(q);
      const matchUserContext = m.rawMemoryV1?.user_context?.toLowerCase().includes(q);

      if (
        !matchTitle &&
        !matchSnippet &&
        !matchFullContent &&
        !matchTranscript &&
        !matchLocation &&
        !matchTags &&
        !matchEntities &&
        !matchCleanText &&
        !matchSummary &&
        !matchUserContext
      ) {
        return false;
      }
    }
    return true;
  });

  const displayCount = totalCount !== undefined ? totalCount : memories.length;

  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.container}>
        {/* Top Header */}
        <View style={styles.topHeader}>
          <View style={styles.logoGroup}>
            <MindMeshLogo size="sm" withText={false} />
            <View>
              <Text style={styles.headerTitle}>Mind Stream</Text>
              <Text style={styles.headerSubtitle}>
                {`${displayCount} Active Memories Ingested`}
              </Text>
            </View>
          </View>

          <View style={styles.headerActionGroup}>
            {onRefreshFeed && (
              <TouchableOpacity
                style={styles.refreshButton}
                onPress={onRefreshFeed}
                disabled={isLoadingFeed}
                activeOpacity={0.8}
              >
                {isLoadingFeed ? (
                  <ActivityIndicator size="small" color="#4A6B53" />
                ) : (
                  <Ionicons name="refresh" size={18} color="#4A6B53" />
                )}
              </TouchableOpacity>
            )}
            <TouchableOpacity
              style={styles.addQuickButton}
              onPress={() => onNavigate('composer')}
              activeOpacity={0.8}
            >
              <Ionicons name="add" size={20} color="#FFFFFF" />
            </TouchableOpacity>
            <TouchableOpacity
              style={styles.profileButton}
              onPress={() => setIsProfileModalOpen(true)}
              activeOpacity={0.8}
            >
              <View style={styles.avatarCircle}>
                <Text style={styles.avatarInitial}>
                  {(user?.name || user?.email || 'U')[0].toUpperCase()}
                </Text>
              </View>
            </TouchableOpacity>
          </View>
        </View>

        {/* Stream Filter Search Box */}
        <View style={styles.searchBox}>
          <Ionicons
            name="search"
            size={18}
            color={searchQuery.trim() ? '#4A6B53' : '#8A9E8F'}
            style={styles.searchIcon}
          />
          <TextInput
            value={searchQuery}
            onChangeText={setSearchQuery}
            placeholder="Search memories in stream..."
            placeholderTextColor="#8A9E8F"
            style={styles.searchInput}
          />
          {searchQuery.length > 0 && (
            <TouchableOpacity onPress={handleClearSearch} style={styles.clearSearchBtn}>
              <Ionicons name="close-circle" size={18} color="#8A9E8F" />
            </TouchableOpacity>
          )}
        </View>

        {/* Filter Pills */}
        <View style={styles.filterContainer}>
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.filterScroll}
          >
            {filterTabs.map((tab) => {
              const isActive = activeFilter === tab.id;
              return (
                <TouchableOpacity
                  key={tab.id}
                  onPress={() => setActiveFilter(tab.id)}
                  style={[styles.filterPill, isActive && styles.filterPillActive]}
                  activeOpacity={0.8}
                >
                  <Text
                    style={[
                      styles.filterPillText,
                      isActive && styles.filterPillTextActive,
                    ]}
                  >
                    {tab.label}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </ScrollView>
        </View>

        {/* Memory Cards Scroll Stream */}
        <ScrollView
          style={styles.cardsStream}
          contentContainerStyle={styles.cardsStreamContent}
          showsVerticalScrollIndicator={false}
          refreshControl={
            onRefreshFeed ? (
              <RefreshControl
                refreshing={isLoadingFeed}
                onRefresh={onRefreshFeed}
                tintColor="#4A6B53"
              />
            ) : undefined
          }
        >
          {/* Shared Workspace Banner */}
          <View style={styles.workspaceBanner}>
            <View>
              <Text style={styles.workspaceTag}>POSTGRESQL MEMORY VAULT</Text>
              <Text style={styles.workspaceTitle}>Active Raw Inputs Feed</Text>
              <Text style={styles.workspaceSubtitle}>
                Live synchronized with PostgreSQL raw_inputs ({displayCount} records)
              </Text>
            </View>
            <Ionicons name="server" size={20} color="#D2E8D7" />
          </View>

          {filteredMemories.length === 0 ? (
            <View style={styles.emptyState}>
              {isLoadingFeed ? (
                <>
                  <ActivityIndicator size="large" color="#4A6B53" />
                  <Text style={styles.emptyStateTitle}>Loading memories from PostgreSQL...</Text>
                </>
              ) : searchQuery.trim() ? (
                <>
                  <Ionicons name="search" size={36} color="#8A9E8F" />
                  <Text style={styles.emptyStateTitle}>No matching memories found</Text>
                  <Text style={styles.emptyStateDesc}>
                    No memories in your stream match "{searchQuery}".
                  </Text>
                </>
              ) : (
                <>
                  <Ionicons name="bulb-outline" size={36} color="#8A9E8F" />
                  <Text style={styles.emptyStateTitle}>No memories found</Text>
                  <Text style={styles.emptyStateDesc}>
                    Tap the (+) button below to ingest your first text, photo, or voice memory.
                  </Text>
                </>
              )}
            </View>
          ) : (
            filteredMemories.map((item) => (
              <TouchableOpacity
                key={item.id}
                onPress={() => {
                  onSelectMemory(item);
                  onNavigate('memory_detail');
                }}
                style={styles.card}
                activeOpacity={0.85}
              >
                {/* Card Top Row */}
                <View style={styles.cardHeader}>
                  <View style={styles.typeBadge}>
                    <Text style={styles.typeBadgeIcon}>
                      {item.type === 'voice' && '🎙️'}
                      {item.type === 'photo' && '📸'}
                      {item.type === 'receipt' && '🧾'}
                      {item.type === 'note' && '📝'}
                    </Text>
                    <Text style={styles.typeBadgeText}>{item.type.toUpperCase()}</Text>
                  </View>
                  <Text style={styles.cardTimestamp}>{item.dateStr}</Text>
                </View>

                {/* Card Title */}
                <Text style={styles.cardTitle} numberOfLines={2}>
                  {item.title}
                </Text>

                {/* Snippet */}
                <Text style={styles.cardSnippet} numberOfLines={3}>
                  {item.snippet}
                </Text>

                {/* Image Preview if Photo */}
                {item.imageUri && (
                  <View style={styles.cardImageContainer}>
                    <Image source={{ uri: item.imageUri }} style={styles.cardImage} />
                  </View>
                )}

                {/* Audio Waveform Indicator if Voice */}
                {item.type === 'voice' && (
                  <View style={styles.audioBar}>
                    <Ionicons name="play-circle" size={24} color="#4A6B53" />
                    <View style={styles.audioWaveform}>
                      {[12, 22, 16, 28, 14, 26, 18, 30, 20, 14, 24, 16].map((h, idx) => (
                        <View key={idx} style={[styles.waveLine, { height: h }]} />
                      ))}
                    </View>
                    <Text style={styles.audioDurationText}>Voice Memo</Text>
                  </View>
                )}

                {/* Card Footer: Location & Tags */}
                <View style={styles.cardFooter}>
                  <View style={styles.locationTag}>
                    <Ionicons name="finger-print-outline" size={12} color="#5E7A64" />
                    <Text style={styles.locationText} numberOfLines={1}>
                      ID: {item.id.slice(0, 8)}...
                    </Text>
                  </View>

                  <View style={styles.tagList}>
                    {item.tags.slice(0, 2).map((tag, idx) => (
                      <View key={idx} style={styles.tagChip}>
                        <Text style={styles.tagText}>#{tag}</Text>
                      </View>
                    ))}
                  </View>
                </View>
              </TouchableOpacity>
            ))
          )}
        </ScrollView>

        {/* User Profile & Account Modal */}
        <Modal visible={isProfileModalOpen} transparent animationType="slide">
          <View style={styles.modalOverlay}>
            <View style={styles.modalSheet}>
              <View style={styles.modalHeader}>
                <Text style={styles.modalTitle}>Sovereign Account</Text>
                <TouchableOpacity onPress={() => setIsProfileModalOpen(false)}>
                  <Ionicons name="close" size={20} color="#5E7A64" />
                </TouchableOpacity>
              </View>

              <View style={styles.profileUserCard}>
                <View style={styles.profileAvatarLg}>
                  <Text style={styles.profileAvatarInitialLg}>
                    {(user?.name || user?.email || 'U')[0].toUpperCase()}
                  </Text>
                </View>
                <View style={styles.profileUserInfo}>
                  <Text style={styles.profileUserName}>{user?.name || 'MindMesh User'}</Text>
                  <Text style={styles.profileUserEmail}>{user?.email || 'sovereign@mindmesh.local'}</Text>
                  <View style={styles.profileIdBadge}>
                    <Ionicons name="key-outline" size={12} color="#4A6B53" />
                    <Text style={styles.profileIdText}>ID: {user?.id || 'U_DEVELOPMENT'}</Text>
                  </View>
                </View>
              </View>

              <View style={styles.profileVaultStatus}>
                <Ionicons name="server-outline" size={16} color="#4A6B53" />
                <Text style={styles.profileVaultText}>
                  PostgreSQL Sovereign Vault Active
                </Text>
              </View>

              <TouchableOpacity
                style={styles.logoutButton}
                onPress={async () => {
                  setIsProfileModalOpen(false);
                  await signOut();
                  onNavigate('login');
                }}
                activeOpacity={0.88}
              >
                <Ionicons name="log-out-outline" size={18} color="#D9534F" />
                <Text style={styles.logoutButtonText}>Sign Out of MindMesh</Text>
              </TouchableOpacity>
            </View>
          </View>
        </Modal>

        {/* Floating Bottom Navigation Dock */}
        <FloatingBottomDock activeScreenId="home" onNavigate={onNavigate} />
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
    paddingTop: 10,
  },
  topHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 10,
  },
  logoGroup: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  headerActionGroup: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  refreshButton: {
    width: 36,
    height: 36,
    borderRadius: 12,
    backgroundColor: '#EBF4ED',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: '#D2E8D7',
  },
  headerTitle: {
    fontSize: 20,
    fontWeight: '800',
    color: '#233529',
    letterSpacing: -0.4,
  },
  headerSubtitle: {
    fontSize: 10,
    fontWeight: '700',
    color: '#5E7A64',
    textTransform: 'uppercase',
    letterSpacing: 0.8,
  },
  addQuickButton: {
    width: 38,
    height: 38,
    borderRadius: 12,
    backgroundColor: '#4A6B53',
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#4A6B53',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.25,
    shadowRadius: 4,
    elevation: 2,
  },
  searchBox: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#D5CDBC',
    paddingLeft: 12,
    paddingRight: 6,
    paddingVertical: 6,
    marginVertical: 8,
  },
  searchIcon: {
    marginRight: 6,
  },
  searchInput: {
    flex: 1,
    fontSize: 13,
    color: '#233529',
    paddingVertical: 4,
  },
  clearSearchBtn: {
    padding: 4,
    marginRight: 4,
  },
  searchSubmitBtn: {
    backgroundColor: '#4A6B53',
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    minWidth: 44,
  },
  searchSubmitBtnDisabled: {
    backgroundColor: '#A8BCAD',
  },
  searchSubmitText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: '700',
  },
  searchLoadingBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#EBF4ED',
    borderWidth: 1,
    borderColor: '#A3D4B0',
    borderRadius: 12,
    padding: 10,
    gap: 10,
    marginVertical: 4,
  },
  searchLoadingTitle: {
    fontSize: 12,
    fontWeight: '700',
    color: '#233529',
  },
  searchLoadingSubtitle: {
    fontSize: 10,
    color: '#5E7A64',
  },
  errorBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FDF2F2',
    borderWidth: 1,
    borderColor: '#F5C6CB',
    borderRadius: 12,
    padding: 10,
    gap: 10,
    marginVertical: 4,
  },
  errorTitle: {
    fontSize: 12,
    fontWeight: '700',
    color: '#D9534F',
  },
  errorSubtitle: {
    fontSize: 10,
    color: '#721C24',
  },
  retryBtn: {
    backgroundColor: '#D9534F',
    paddingVertical: 4,
    paddingHorizontal: 10,
    borderRadius: 8,
  },
  retryBtnText: {
    color: '#FFFFFF',
    fontSize: 11,
    fontWeight: '700',
  },
  answerCard: {
    backgroundColor: '#233529',
    borderRadius: 20,
    padding: 18,
    gap: 10,
    shadowColor: '#233529',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.25,
    shadowRadius: 8,
    elevation: 3,
  },
  answerHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  answerBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: '#4A6B53',
    paddingVertical: 4,
    paddingHorizontal: 10,
    borderRadius: 10,
  },
  answerBadgeText: {
    color: '#FFFFFF',
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 0.8,
  },
  dismissSearchBtn: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: '#354E3C',
    alignItems: 'center',
    justifyContent: 'center',
  },
  answerQuery: {
    fontSize: 13,
    fontStyle: 'italic',
    color: '#A3D4B0',
  },
  answerBody: {
    fontSize: 14,
    color: '#FFFFFF',
    lineHeight: 21,
    fontWeight: '500',
  },
  answerFooter: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    borderTopWidth: 1,
    borderTopColor: '#354E3C',
    paddingTop: 8,
    marginTop: 4,
  },
  answerFooterText: {
    fontSize: 10,
    color: '#A3D4B0',
    fontWeight: '600',
  },
  noMemoryCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    padding: 24,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: '#E5DFD5',
    gap: 12,
  },
  noMemoryHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    width: '100%',
  },
  noMemoryTitle: {
    fontSize: 16,
    fontWeight: '800',
    color: '#233529',
    textAlign: 'center',
  },
  noMemorySubtitle: {
    fontSize: 13,
    color: '#5E7A64',
    textAlign: 'center',
    lineHeight: 19,
  },
  returnToStreamBtn: {
    backgroundColor: '#4A6B53',
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: 12,
    marginTop: 8,
  },
  returnToStreamText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: '700',
  },
  sourcesHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 4,
    paddingTop: 8,
  },
  sourcesTitle: {
    fontSize: 11,
    fontWeight: '800',
    color: '#5E7A64',
    letterSpacing: 1.0,
  },
  sourcesReturnText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#4A6B53',
    textDecorationLine: 'underline',
  },
  filterContainer: {
    marginVertical: 4,
  },
  filterScroll: {
    gap: 8,
    paddingRight: 8,
  },
  filterPill: {
    paddingVertical: 7,
    paddingHorizontal: 14,
    borderRadius: 12,
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#E5DFD5',
  },
  filterPillActive: {
    backgroundColor: '#4A6B53',
    borderColor: '#4A6B53',
  },
  filterPillText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#233529',
  },
  filterPillTextActive: {
    color: '#FFFFFF',
  },
  cardsStream: {
    flex: 1,
    marginTop: 6,
  },
  cardsStreamContent: {
    paddingBottom: 110,
    gap: 12,
  },
  workspaceBanner: {
    backgroundColor: '#4A6B53',
    borderRadius: 20,
    padding: 16,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    shadowColor: '#4A6B53',
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.2,
    shadowRadius: 6,
    elevation: 2,
  },
  workspaceTag: {
    fontSize: 9,
    fontWeight: '800',
    color: '#A3D4B0',
    letterSpacing: 1.2,
  },
  workspaceTitle: {
    fontSize: 15,
    fontWeight: '800',
    color: '#FFFFFF',
    marginTop: 2,
  },
  workspaceSubtitle: {
    fontSize: 11,
    color: '#E0F0E4',
    marginTop: 2,
  },
  card: {
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    padding: 16,
    borderWidth: 1,
    borderColor: '#E5DFD5',
    gap: 10,
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 6,
    elevation: 1,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  typeBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    backgroundColor: '#FAF7F0',
    paddingVertical: 3,
    paddingHorizontal: 8,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#D5CDBC',
  },
  typeBadgeIcon: {
    fontSize: 11,
  },
  typeBadgeText: {
    fontSize: 9,
    fontWeight: '800',
    color: '#4A6B53',
    letterSpacing: 0.5,
  },
  similarityBadge: {
    backgroundColor: '#EBF4ED',
    paddingVertical: 3,
    paddingHorizontal: 8,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#A3D4B0',
  },
  similarityText: {
    fontSize: 9,
    fontWeight: '700',
    color: '#2D5B3A',
  },
  cardTimestamp: {
    fontSize: 11,
    color: '#5E7A64',
    fontWeight: '500',
  },
  userContextBox: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FAF7F0',
    padding: 8,
    borderRadius: 10,
    gap: 6,
    borderLeftWidth: 3,
    borderLeftColor: '#4A6B53',
  },
  userContextLabel: {
    fontWeight: '800',
    color: '#233529',
  },
  userContextText: {
    fontSize: 11,
    color: '#425547',
    flex: 1,
  },
  cardTitle: {
    fontSize: 15,
    fontWeight: '800',
    color: '#233529',
    lineHeight: 20,
  },
  cardSnippet: {
    fontSize: 12,
    color: '#425547',
    lineHeight: 18,
  },
  cardImageContainer: {
    height: 140,
    borderRadius: 14,
    overflow: 'hidden',
    backgroundColor: '#F0ECE1',
    marginTop: 4,
  },
  imageEvidenceBox: {
    borderRadius: 14,
    overflow: 'hidden',
    marginTop: 4,
  },
  cardImage: {
    width: '100%',
    height: 140,
    resizeMode: 'cover',
  },
  mediaMetadataBox: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FAF7F0',
    borderWidth: 1,
    borderColor: '#D5CDBC',
    borderRadius: 12,
    padding: 12,
    gap: 10,
  },
  mediaMetadataTitle: {
    fontSize: 12,
    fontWeight: '700',
    color: '#233529',
  },
  mediaMetadataSub: {
    fontSize: 10,
    color: '#5E7A64',
    marginTop: 2,
  },
  audioEvidenceBox: {
    gap: 4,
    marginTop: 4,
  },
  audioBar: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FAF7F0',
    padding: 10,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#D5CDBC',
    gap: 10,
  },
  audioWaveform: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 3,
    height: 30,
  },
  waveLine: {
    width: 3,
    backgroundColor: '#4A6B53',
    borderRadius: 2,
  },
  audioDurationText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#5E7A64',
  },
  audioFilenameText: {
    fontSize: 10,
    color: '#5E7A64',
    paddingHorizontal: 4,
  },
  cardFooter: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: '#F0ECE1',
  },
  locationTag: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    maxWidth: '50%',
  },
  locationText: {
    fontSize: 10,
    color: '#5E7A64',
    fontWeight: '600',
  },
  tagList: {
    flexDirection: 'row',
    gap: 6,
  },
  tagChip: {
    backgroundColor: '#FAF7F0',
    paddingVertical: 2,
    paddingHorizontal: 7,
    borderRadius: 6,
  },
  tagText: {
    fontSize: 10,
    fontWeight: '700',
    color: '#4A6B53',
  },
  tapToViewText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#4A6B53',
  },
  emptyState: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 48,
    paddingHorizontal: 24,
    gap: 10,
  },
  emptyStateTitle: {
    fontSize: 16,
    fontWeight: '800',
    color: '#233529',
  },
  emptyStateDesc: {
    fontSize: 12,
    color: '#5E7A64',
    textAlign: 'center',
    lineHeight: 18,
  },
  profileButton: {
    width: 38,
    height: 38,
    borderRadius: 12,
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#D5CDBC',
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarCircle: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: '#EBF4ED',
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarInitial: {
    fontSize: 13,
    fontWeight: '800',
    color: '#4A6B53',
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(35, 53, 41, 0.45)',
    justifyContent: 'flex-end',
  },
  modalSheet: {
    backgroundColor: '#FAF7F0',
    borderTopLeftRadius: 28,
    borderTopRightRadius: 28,
    padding: 24,
    gap: 16,
    borderWidth: 1,
    borderColor: '#E5DFD5',
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: '800',
    color: '#233529',
    letterSpacing: -0.3,
  },
  profileUserCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#E5DFD5',
    borderRadius: 20,
    padding: 16,
    gap: 14,
  },
  profileAvatarLg: {
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: '#EBF4ED',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: '#D2E8D7',
  },
  profileAvatarInitialLg: {
    fontSize: 22,
    fontWeight: '800',
    color: '#4A6B53',
  },
  profileUserInfo: {
    flex: 1,
    gap: 2,
  },
  profileUserName: {
    fontSize: 16,
    fontWeight: '700',
    color: '#233529',
  },
  profileUserEmail: {
    fontSize: 12,
    color: '#5E7A64',
  },
  profileIdBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginTop: 4,
  },
  profileIdText: {
    fontSize: 11,
    fontWeight: '600',
    color: '#4A6B53',
  },
  profileVaultStatus: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#EBF4ED',
    borderWidth: 1,
    borderColor: '#D2E8D7',
    borderRadius: 14,
    padding: 12,
    gap: 8,
  },
  profileVaultText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#233529',
  },
  logoutButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FDF2F2',
    borderWidth: 1,
    borderColor: '#F5C6CB',
    borderRadius: 18,
    paddingVertical: 14,
    gap: 8,
    marginTop: 4,
  },
  logoutButtonText: {
    fontSize: 14,
    fontWeight: '700',
    color: '#D9534F',
  },
});
