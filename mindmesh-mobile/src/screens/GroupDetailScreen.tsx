import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
  RefreshControl,
  Modal,
  Alert,
  ScrollView,
  Share,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Group, GroupMember, GroupInvitation, GroupRole, RawFeedItem, ScreenId } from '../types';
import {
  getGroupDetails,
  getRawFeed,
  getGroupMembers,
  getGroupInvitations,
  createInvitation,
  revokeInvitation,
  updateMemberRole,
  removeMember,
  leaveGroup,
  deleteGroup,
  transferGroupOwnership,
  searchUsers,
} from '../services/apiClient';

interface GroupDetailScreenProps {
  groupId: string;
  onNavigate: (screen: ScreenId, params?: any) => void;
  onSelectMemory?: (item: any) => void;
}

type TabType = 'feed' | 'members' | 'invitations' | 'settings';

export const GroupDetailScreen: React.FC<GroupDetailScreenProps> = ({
  groupId,
  onNavigate,
  onSelectMemory,
}) => {
  const [group, setGroup] = useState<Group | null>(null);
  const [activeTab, setActiveTab] = useState<TabType>('feed');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Tab data
  const [feedItems, setFeedItems] = useState<RawFeedItem[]>([]);
  const [members, setMembers] = useState<GroupMember[]>([]);
  const [invitations, setInvitations] = useState<GroupInvitation[]>([]);

  // Invite Modal
  const [inviteModalVisible, setInviteModalVisible] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState<GroupRole>('MEMBER');
  const [inviting, setInviting] = useState(false);
  const [generatedToken, setGeneratedToken] = useState<string | null>(null);

  // Role Edit Modal
  const [roleModalVisible, setRoleModalVisible] = useState(false);
  const [selectedMember, setSelectedMember] = useState<GroupMember | null>(null);
  const [newRole, setNewRole] = useState<GroupRole>('MEMBER');

  // Transfer Ownership Modal
  const [transferModalVisible, setTransferModalVisible] = useState(false);
  const [newOwnerId, setNewOwnerId] = useState('');
  const [transferring, setTransferring] = useState(false);

  const isOwner = group?.my_role === 'OWNER';
  const isAdmin = isOwner || group?.my_role === 'ADMIN';

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const groupData = await getGroupDetails(groupId);
      setGroup(groupData);

      // Load active tab data
      if (activeTab === 'feed') {
        const feedRes = await getRawFeed(100, 0, groupId);
        setFeedItems(feedRes.items || []);
      } else if (activeTab === 'members') {
        const memberList = await getGroupMembers(groupId);
        setMembers(memberList);
      } else if (activeTab === 'invitations') {
        if (isAdmin) {
          const invList = await getGroupInvitations(groupId);
          setInvitations(invList);
        }
      }
    } catch (err: any) {
      Alert.alert('Error', err?.message || 'Failed to load group details');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [groupId, activeTab, isAdmin]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const onRefresh = () => {
    setRefreshing(true);
    loadData();
  };

  const handleShareInvite = async (token: string, groupName: string) => {
    try {
      const deepLink = `mindmesh://invite/${token}`;
      const webUrl = `http://10.9.11.238:8002/api/v1/groups/invitations/validate/${token}`;
      await Share.share({
        title: `Join ${groupName} on MindMesh`,
        message: `You've been invited to join "${groupName}" on MindMesh.\n\nOpen in MindMesh: ${deepLink}\nWeb details: ${webUrl}\n\nToken: ${token}`,
      });
    } catch (err: any) {
      Alert.alert('Share Failed', err?.message || 'Unable to open share sheet');
    }
  };

  const handleSendInvite = async () => {
    if (!inviteEmail.trim()) {
      Alert.alert('Validation Error', 'Email or invitee identifier is required.');
      return;
    }
    setInviting(true);
    try {
      const inv = await createInvitation(groupId, inviteEmail, inviteRole);
      const token = inv.invitation_token || '';
      setGeneratedToken(token);
      setInviteEmail('');
      setInviteModalVisible(false);
      loadData();
      Alert.alert(
        'Invitation Created',
        `Invitation created for ${inv.invitee_email || 'user'}.\nToken: ${token}`,
        [
          { text: 'Done', style: 'cancel' },
          {
            text: 'Share Link',
            onPress: () => handleShareInvite(token, group?.name || 'Group'),
          },
        ]
      );
    } catch (err: any) {
      Alert.alert('Error', err?.message || 'Failed to create invitation');
    } finally {
      setInviting(false);
    }
  };

  const handleRevokeInvite = async (invitationId: string) => {
    try {
      await revokeInvitation(invitationId);
      setInvitations((prev) => prev.filter((i) => i.id !== invitationId));
      Alert.alert('Success', 'Invitation revoked');
    } catch (err: any) {
      Alert.alert('Error', err?.message || 'Failed to revoke invitation');
    }
  };

  const handleUpdateRole = async () => {
    if (!selectedMember) return;
    try {
      await updateMemberRole(groupId, selectedMember.user_id, newRole);
      setMembers((prev) =>
        prev.map((m) => (m.user_id === selectedMember.user_id ? { ...m, role: newRole } : m))
      );
      setRoleModalVisible(false);
      Alert.alert('Success', `Updated role to ${newRole}`);
    } catch (err: any) {
      Alert.alert('Error', err?.message || 'Failed to update member role');
    }
  };

  const handleRemoveMember = (member: GroupMember) => {
    Alert.alert(
      'Remove Member',
      `Are you sure you want to remove ${member.username} from this group?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Remove',
          style: 'destructive',
          onPress: async () => {
            try {
              await removeMember(groupId, member.user_id);
              setMembers((prev) => prev.filter((m) => m.user_id !== member.user_id));
              Alert.alert('Success', `${member.username} removed`);
            } catch (err: any) {
              Alert.alert('Error', err?.message || 'Failed to remove member');
            }
          },
        },
      ]
    );
  };

  const handleLeaveGroup = () => {
    Alert.alert(
      'Leave Group',
      'Are you sure you want to leave this group? You will lose access to its collaborative feed and memories.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Leave',
          style: 'destructive',
          onPress: async () => {
            try {
              await leaveGroup(groupId);
              Alert.alert('Left Group', 'You have left the group.');
              onNavigate('groups');
            } catch (err: any) {
              Alert.alert('Error', err?.message || 'Failed to leave group');
            }
          },
        },
      ]
    );
  };

  const handleDeleteGroup = () => {
    Alert.alert(
      'Delete Group',
      'This will permanently delete the group and revoke all shared access. This action cannot be undone.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete Group',
          style: 'destructive',
          onPress: async () => {
            try {
              await deleteGroup(groupId);
              Alert.alert('Deleted', 'Group successfully deleted.');
              onNavigate('groups');
            } catch (err: any) {
              Alert.alert('Error', err?.message || 'Failed to delete group');
            }
          },
        },
      ]
    );
  };

  const handleTransferOwnership = async () => {
    if (!newOwnerId.trim()) {
      Alert.alert('Validation Error', 'Target new owner user ID is required.');
      return;
    }
    setTransferring(true);
    try {
      await transferGroupOwnership(groupId, newOwnerId.trim());
      Alert.alert('Success', 'Ownership transferred successfully.');
      setTransferModalVisible(false);
      loadData();
    } catch (err: any) {
      Alert.alert('Error', err?.message || 'Failed to transfer ownership');
    } finally {
      setTransferring(false);
    }
  };

  const renderFeedItem = ({ item }: { item: RawFeedItem }) => {
    const memory = item.structured_payload;
    const title =
      memory?.content?.summary ||
      memory?.content?.clean_text?.substring(0, 80) ||
      item.raw_payload?.substring(0, 80) ||
      'Collaborative Memory';

    return (
      <TouchableOpacity
        style={styles.feedCard}
        activeOpacity={0.85}
        onPress={() => {
          if (onSelectMemory) {
            onSelectMemory(item);
          }
        }}
      >
        <View style={styles.feedCardHeader}>
          <View style={styles.mediaTypeBadge}>
            <Ionicons
              name={
                item.media_type === 'image'
                  ? 'image-outline'
                  : item.media_type === 'audio'
                  ? 'mic-outline'
                  : 'document-text-outline'
              }
              size={14}
              color="#4A6B53"
            />
            <Text style={styles.mediaTypeText}>{item.media_type.toUpperCase()}</Text>
          </View>
          <Text style={styles.feedDate}>
            {new Date(item.received_at).toLocaleDateString(undefined, {
              month: 'short',
              day: 'numeric',
            })}
          </Text>
        </View>
        <Text style={styles.feedTitle} numberOfLines={2}>
          {title}
        </Text>
      </TouchableOpacity>
    );
  };

  const renderMemberItem = ({ item }: { item: GroupMember }) => (
    <View style={styles.memberCard}>
      <View style={styles.memberAvatar}>
        <Text style={styles.memberAvatarText}>
          {item.username.substring(0, 2).toUpperCase()}
        </Text>
      </View>
      <View style={styles.memberInfo}>
        <Text style={styles.memberName}>{item.username}</Text>
        <Text style={styles.memberJoined}>
          Joined {new Date(item.joined_at).toLocaleDateString()}
        </Text>
      </View>
      <View style={styles.memberRoleContainer}>
        <View style={styles.roleTag}>
          <Text style={styles.roleTagText}>{item.role}</Text>
        </View>
        {isAdmin && item.role !== 'OWNER' && (
          <TouchableOpacity
            style={styles.roleEditBtn}
            onPress={() => {
              setSelectedMember(item);
              setNewRole(item.role);
              setRoleModalVisible(true);
            }}
          >
            <Ionicons name="create-outline" size={16} color="#4A6B53" />
          </TouchableOpacity>
        )}
        {isAdmin && item.role !== 'OWNER' && (
          <TouchableOpacity
            style={styles.removeMemberBtn}
            onPress={() => handleRemoveMember(item)}
          >
            <Ionicons name="trash-outline" size={16} color="#D9534F" />
          </TouchableOpacity>
        )}
      </View>
    </View>
  );

  const renderInvitationItem = ({ item }: { item: GroupInvitation }) => (
    <View style={styles.inviteCard}>
      <View style={styles.inviteInfo}>
        <Text style={styles.inviteEmail}>{item.invitee_email}</Text>
        <Text style={styles.inviteMeta}>
          Role: {item.role} · Status: {item.status.toUpperCase()}
        </Text>
        {item.invitation_token && (
          <Text style={styles.inviteToken} numberOfLines={1}>
            Token: {item.invitation_token}
          </Text>
        )}
      </View>
      <View style={styles.inviteActionRow}>
        {item.status === 'pending' && item.invitation_token && (
          <TouchableOpacity
            style={styles.shareInviteBtn}
            onPress={() => handleShareInvite(item.invitation_token!, group?.name || 'Group')}
          >
            <Ionicons name="share-social-outline" size={14} color="#4A6B53" />
            <Text style={styles.shareInviteBtnText}>Share</Text>
          </TouchableOpacity>
        )}
        {item.status === 'pending' && (
          <TouchableOpacity
            style={styles.revokeBtn}
            onPress={() => handleRevokeInvite(item.id)}
          >
            <Text style={styles.revokeBtnText}>Revoke</Text>
          </TouchableOpacity>
        )}
      </View>
    </View>
  );

  return (
    <View style={styles.container}>
      {/* Top Bar */}
      <View style={styles.topBar}>
        <TouchableOpacity style={styles.backButton} onPress={() => onNavigate('groups')}>
          <Ionicons name="arrow-back" size={22} color="#1F2923" />
        </TouchableOpacity>
        <View style={styles.headerTitleArea}>
          <Text style={styles.topBarTitle} numberOfLines={1}>
            {group?.name || 'Group Details'}
          </Text>
          <Text style={styles.roleIndicator}>Role: {group?.my_role || 'MEMBER'}</Text>
        </View>
        <TouchableOpacity
          style={styles.actionIcon}
          onPress={() => onNavigate('composer', { groupId })}
        >
          <Ionicons name="add-circle" size={26} color="#4A6B53" />
        </TouchableOpacity>
      </View>

      {/* Tabs */}
      <View style={styles.tabBar}>
        {(['feed', 'members', 'invitations', 'settings'] as TabType[]).map((tab) => {
          if (tab === 'invitations' && !isAdmin) return null;
          return (
            <TouchableOpacity
              key={tab}
              style={[styles.tabButton, activeTab === tab && styles.tabButtonActive]}
              onPress={() => setActiveTab(tab)}
            >
              <Text style={[styles.tabButtonText, activeTab === tab && styles.tabButtonTextActive]}>
                {tab.charAt(0).toUpperCase() + tab.slice(1)}
              </Text>
            </TouchableOpacity>
          );
        })}
      </View>

      {/* Tab Contents */}
      {loading ? (
        <View style={styles.centerContainer}>
          <ActivityIndicator size="large" color="#4A6B53" />
        </View>
      ) : activeTab === 'feed' ? (
        feedItems.length === 0 ? (
          <View style={styles.centerContainer}>
            <Ionicons name="file-tray-outline" size={40} color="#8B9E90" />
            <Text style={styles.emptyText}>No memories shared with this group yet.</Text>
            <TouchableOpacity
              style={styles.shareMemoryBtn}
              onPress={() => onNavigate('composer', { groupId })}
            >
              <Text style={styles.shareMemoryBtnText}>Post First Memory</Text>
            </TouchableOpacity>
          </View>
        ) : (
          <FlatList
            data={feedItems}
            keyExtractor={(item) => item.id}
            renderItem={renderFeedItem}
            contentContainerStyle={styles.listContainer}
            refreshControl={
              <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#4A6B53" />
            }
          />
        )
      ) : activeTab === 'members' ? (
        <FlatList
          data={members}
          keyExtractor={(item) => item.id}
          renderItem={renderMemberItem}
          contentContainerStyle={styles.listContainer}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#4A6B53" />
          }
        />
      ) : activeTab === 'invitations' ? (
        <View style={styles.flexOne}>
          <View style={styles.inviteHeaderBar}>
            <Text style={styles.inviteCountText}>{invitations.length} Invitations</Text>
            <TouchableOpacity
              style={styles.newInviteBtn}
              onPress={() => setInviteModalVisible(true)}
            >
              <Ionicons name="add" size={16} color="#FFFFFF" />
              <Text style={styles.newInviteBtnText}>Invite User</Text>
            </TouchableOpacity>
          </View>
          <FlatList
            data={invitations}
            keyExtractor={(item) => item.id}
            renderItem={renderInvitationItem}
            contentContainerStyle={styles.listContainer}
            refreshControl={
              <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#4A6B53" />
            }
          />
        </View>
      ) : (
        /* Settings Tab */
        <ScrollView style={styles.settingsContainer}>
          <View style={styles.settingsSection}>
            <Text style={styles.settingsSectionTitle}>Group Information</Text>
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>Name</Text>
              <Text style={styles.infoValue}>{group?.name}</Text>
            </View>
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>Description</Text>
              <Text style={styles.infoValue}>{group?.description || 'None'}</Text>
            </View>
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>Your Role</Text>
              <Text style={styles.infoValue}>{group?.my_role}</Text>
            </View>
          </View>

          <View style={styles.settingsSection}>
            <Text style={styles.settingsSectionTitle}>Actions</Text>
            <TouchableOpacity style={styles.settingsActionBtn} onPress={handleLeaveGroup}>
              <Ionicons name="exit-outline" size={18} color="#D9534F" />
              <Text style={styles.settingsActionTextDanger}>Leave Group</Text>
            </TouchableOpacity>

            {isOwner && (
              <TouchableOpacity
                style={styles.settingsActionBtn}
                onPress={() => setTransferModalVisible(true)}
              >
                <Ionicons name="swap-horizontal-outline" size={18} color="#4A6B53" />
                <Text style={styles.settingsActionText}>Transfer Ownership</Text>
              </TouchableOpacity>
            )}

            {isOwner && (
              <TouchableOpacity style={styles.settingsActionBtn} onPress={handleDeleteGroup}>
                <Ionicons name="trash-outline" size={18} color="#D9534F" />
                <Text style={styles.settingsActionTextDanger}>Delete Group Permanently</Text>
              </TouchableOpacity>
            )}
          </View>
        </ScrollView>
      )}

      {/* Role Change Modal */}
      <Modal visible={roleModalVisible} transparent animationType="fade">
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>Change Member Role</Text>
            <Text style={styles.modalSub}>Member: {selectedMember?.username}</Text>
            {(['ADMIN', 'CONTRIBUTOR', 'MEMBER', 'GUEST'] as GroupRole[]).map((r) => (
              <TouchableOpacity
                key={r}
                style={[styles.roleSelectOption, newRole === r && styles.roleSelectOptionActive]}
                onPress={() => setNewRole(r)}
              >
                <Text
                  style={[styles.roleOptionText, newRole === r && styles.roleOptionTextActive]}
                >
                  {r}
                </Text>
                {newRole === r && <Ionicons name="checkmark" size={18} color="#4A6B53" />}
              </TouchableOpacity>
            ))}
            <View style={styles.modalBtnRow}>
              <TouchableOpacity
                style={styles.cancelBtn}
                onPress={() => setRoleModalVisible(false)}
              >
                <Text style={styles.cancelBtnText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.submitBtn} onPress={handleUpdateRole}>
                <Text style={styles.submitBtnText}>Save Role</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* Send Invite Modal */}
      <Modal visible={inviteModalVisible} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>Send Group Invitation</Text>
            <Text style={styles.inputLabel}>Invitee Email / Identifier</Text>
            <TextInput
              style={styles.input}
              placeholder="e.g. colleague@company.com"
              placeholderTextColor="#8B9E90"
              value={inviteEmail}
              onChangeText={setInviteEmail}
              autoCapitalize="none"
            />
            <Text style={styles.inputLabel}>Assigned Role</Text>
            <View style={styles.roleChipRow}>
              {(['ADMIN', 'CONTRIBUTOR', 'MEMBER', 'GUEST'] as GroupRole[]).map((r) => (
                <TouchableOpacity
                  key={r}
                  style={[styles.roleChip, inviteRole === r && styles.roleChipActive]}
                  onPress={() => setInviteRole(r)}
                >
                  <Text
                    style={[styles.roleChipText, inviteRole === r && styles.roleChipTextActive]}
                  >
                    {r}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
            <View style={styles.modalBtnRow}>
              <TouchableOpacity
                style={styles.cancelBtn}
                onPress={() => setInviteModalVisible(false)}
                disabled={inviting}
              >
                <Text style={styles.cancelBtnText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.submitBtn}
                onPress={handleSendInvite}
                disabled={inviting}
              >
                {inviting ? (
                  <ActivityIndicator size="small" color="#FFFFFF" />
                ) : (
                  <Text style={styles.submitBtnText}>Create Invite</Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* Transfer Ownership Modal */}
      <Modal visible={transferModalVisible} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>Transfer Group Ownership</Text>
            <Text style={styles.modalSub}>
              Enter the User ID of an existing active group member. You will be demoted to Admin.
            </Text>
            <TextInput
              style={styles.input}
              placeholder="Target User ID"
              placeholderTextColor="#8B9E90"
              value={newOwnerId}
              onChangeText={setNewOwnerId}
              autoCapitalize="none"
            />
            <View style={styles.modalBtnRow}>
              <TouchableOpacity
                style={styles.cancelBtn}
                onPress={() => setTransferModalVisible(false)}
                disabled={transferring}
              >
                <Text style={styles.cancelBtnText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.submitBtn}
                onPress={handleTransferOwnership}
                disabled={transferring}
              >
                {transferring ? (
                  <ActivityIndicator size="small" color="#FFFFFF" />
                ) : (
                  <Text style={styles.submitBtnText}>Transfer</Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#FAF7F0',
  },
  flexOne: {
    flex: 1,
  },
  topBar: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingTop: 52,
    paddingBottom: 14,
    backgroundColor: '#FFFFFF',
    borderBottomWidth: 1,
    borderBottomColor: '#E2DDD2',
  },
  backButton: {
    padding: 6,
    marginRight: 8,
  },
  headerTitleArea: {
    flex: 1,
  },
  topBarTitle: {
    fontSize: 18,
    fontWeight: '800',
    color: '#1F2923',
  },
  roleIndicator: {
    fontSize: 11,
    color: '#5E7A64',
    fontWeight: '600',
  },
  actionIcon: {
    padding: 4,
  },
  tabBar: {
    flexDirection: 'row',
    backgroundColor: '#FFFFFF',
    borderBottomWidth: 1,
    borderBottomColor: '#E2DDD2',
    paddingHorizontal: 16,
  },
  tabButton: {
    paddingVertical: 12,
    paddingHorizontal: 14,
    borderBottomWidth: 2,
    borderBottomColor: 'transparent',
  },
  tabButtonActive: {
    borderBottomColor: '#4A6B53',
  },
  tabButtonText: {
    fontSize: 13,
    fontWeight: '700',
    color: '#8B9E90',
  },
  tabButtonTextActive: {
    color: '#4A6B53',
  },
  listContainer: {
    padding: 16,
    paddingBottom: 100,
  },
  feedCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 14,
    padding: 14,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: '#E2DDD2',
  },
  feedCardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  mediaTypeBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#EAF2EC',
    paddingVertical: 3,
    paddingHorizontal: 8,
    borderRadius: 6,
    gap: 4,
  },
  mediaTypeText: {
    fontSize: 10,
    fontWeight: '800',
    color: '#4A6B53',
  },
  feedDate: {
    fontSize: 12,
    color: '#8B9E90',
  },
  feedTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#1F2923',
    lineHeight: 20,
  },
  memberCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderRadius: 14,
    padding: 12,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: '#E2DDD2',
    gap: 12,
  },
  memberAvatar: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: '#EAF2EC',
    alignItems: 'center',
    justifyContent: 'center',
  },
  memberAvatarText: {
    fontSize: 13,
    fontWeight: '800',
    color: '#4A6B53',
  },
  memberInfo: {
    flex: 1,
  },
  memberName: {
    fontSize: 14,
    fontWeight: '700',
    color: '#1F2923',
  },
  memberJoined: {
    fontSize: 11,
    color: '#8B9E90',
  },
  memberRoleContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  roleTag: {
    backgroundColor: '#FAF7F0',
    borderWidth: 1,
    borderColor: '#D5CDBC',
    paddingVertical: 3,
    paddingHorizontal: 7,
    borderRadius: 6,
  },
  roleTagText: {
    fontSize: 10,
    fontWeight: '800',
    color: '#4A6B53',
  },
  roleEditBtn: {
    padding: 4,
  },
  removeMemberBtn: {
    padding: 4,
  },
  inviteHeaderBar: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  inviteCountText: {
    fontSize: 13,
    fontWeight: '700',
    color: '#5E7A64',
  },
  newInviteBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#4A6B53',
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 16,
    gap: 4,
  },
  newInviteBtnText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: '700',
  },
  inviteCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderRadius: 14,
    padding: 12,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: '#E2DDD2',
  },
  inviteInfo: {
    flex: 1,
  },
  inviteEmail: {
    fontSize: 14,
    fontWeight: '700',
    color: '#1F2923',
  },
  inviteMeta: {
    fontSize: 11,
    color: '#5E7A64',
    marginTop: 2,
  },
  inviteToken: {
    fontSize: 10,
    color: '#8B9E90',
    marginTop: 4,
  },
  inviteActionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  shareInviteBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 5,
    paddingHorizontal: 10,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#4A6B53',
    backgroundColor: '#F0ECE4',
    gap: 4,
  },
  shareInviteBtnText: {
    color: '#4A6B53',
    fontSize: 11,
    fontWeight: '700',
  },
  revokeBtn: {
    paddingVertical: 5,
    paddingHorizontal: 10,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#D9534F',
  },
  revokeBtnText: {
    color: '#D9534F',
    fontSize: 11,
    fontWeight: '700',
  },
  settingsContainer: {
    padding: 16,
  },
  settingsSection: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 16,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#E2DDD2',
  },
  settingsSectionTitle: {
    fontSize: 14,
    fontWeight: '800',
    color: '#1F2923',
    marginBottom: 12,
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#F0ECE4',
  },
  infoLabel: {
    fontSize: 13,
    color: '#5E7A64',
  },
  infoValue: {
    fontSize: 13,
    fontWeight: '700',
    color: '#1F2923',
  },
  settingsActionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    gap: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#F0ECE4',
  },
  settingsActionText: {
    fontSize: 14,
    fontWeight: '700',
    color: '#4A6B53',
  },
  settingsActionTextDanger: {
    fontSize: 14,
    fontWeight: '700',
    color: '#D9534F',
  },
  centerContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 32,
  },
  emptyText: {
    marginTop: 12,
    fontSize: 14,
    color: '#5E7A64',
    textAlign: 'center',
  },
  shareMemoryBtn: {
    marginTop: 16,
    backgroundColor: '#4A6B53',
    paddingVertical: 10,
    paddingHorizontal: 20,
    borderRadius: 20,
  },
  shareMemoryBtnText: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 13,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.45)',
    justifyContent: 'center',
    padding: 24,
  },
  modalContent: {
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    padding: 20,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: '800',
    color: '#1F2923',
    marginBottom: 6,
  },
  modalSub: {
    fontSize: 13,
    color: '#5E7A64',
    marginBottom: 16,
  },
  roleSelectOption: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 12,
    paddingHorizontal: 14,
    borderRadius: 12,
    backgroundColor: '#FAF7F0',
    marginBottom: 8,
  },
  roleSelectOptionActive: {
    backgroundColor: '#EAF2EC',
    borderWidth: 1,
    borderColor: '#4A6B53',
  },
  roleOptionText: {
    fontSize: 14,
    fontWeight: '700',
    color: '#1F2923',
  },
  roleOptionTextActive: {
    color: '#4A6B53',
  },
  inputLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: '#5E7A64',
    marginBottom: 6,
    marginTop: 10,
  },
  input: {
    backgroundColor: '#FAF7F0',
    borderWidth: 1,
    borderColor: '#D5CDBC',
    borderRadius: 12,
    padding: 12,
    fontSize: 14,
    color: '#1F2923',
    marginBottom: 10,
  },
  roleChipRow: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 16,
  },
  roleChip: {
    flex: 1,
    paddingVertical: 8,
    borderRadius: 10,
    backgroundColor: '#FAF7F0',
    borderWidth: 1,
    borderColor: '#D5CDBC',
    alignItems: 'center',
  },
  roleChipActive: {
    backgroundColor: '#4A6B53',
    borderColor: '#4A6B53',
  },
  roleChipText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#5E7A64',
  },
  roleChipTextActive: {
    color: '#FFFFFF',
  },
  modalBtnRow: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 12,
    marginTop: 16,
  },
  cancelBtn: {
    paddingVertical: 10,
    paddingHorizontal: 18,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: '#D5CDBC',
  },
  cancelBtnText: {
    color: '#5E7A64',
    fontWeight: '700',
    fontSize: 13,
  },
  submitBtn: {
    backgroundColor: '#4A6B53',
    paddingVertical: 10,
    paddingHorizontal: 20,
    borderRadius: 20,
  },
  submitBtnText: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 13,
  },
});
