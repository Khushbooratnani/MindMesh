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
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Group, GroupRole, ScreenId } from '../types';
import { getGroups, createGroup, acceptInvitation } from '../services/apiClient';

interface GroupsScreenProps {
  onNavigate: (screen: ScreenId, params?: { groupId?: string }) => void;
  onSelectGroup: (group: Group) => void;
}

export const GroupsScreen: React.FC<GroupsScreenProps> = ({ onNavigate, onSelectGroup }) => {
  const [groups, setGroups] = useState<Group[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Create Group Modal
  const [createModalVisible, setCreateModalVisible] = useState(false);
  const [newGroupName, setNewGroupName] = useState('');
  const [newGroupDesc, setNewGroupDesc] = useState('');
  const [creating, setCreating] = useState(false);

  // Accept Invite Modal
  const [inviteModalVisible, setInviteModalVisible] = useState(false);
  const [inviteToken, setInviteToken] = useState('');
  const [accepting, setAccepting] = useState(false);

  const fetchGroups = useCallback(async () => {
    try {
      setError(null);
      const data = await getGroups();
      setGroups(data);
    } catch (err: any) {
      setError(err?.message || 'Failed to load collaborative groups');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchGroups();
  }, [fetchGroups]);

  const onRefresh = () => {
    setRefreshing(true);
    fetchGroups();
  };

  const handleCreateGroup = async () => {
    if (!newGroupName.trim()) {
      Alert.alert('Validation Error', 'Group name is required.');
      return;
    }
    setCreating(true);
    try {
      const created = await createGroup(newGroupName, newGroupDesc);
      setGroups((prev) => [created, ...prev]);
      setCreateModalVisible(false);
      setNewGroupName('');
      setNewGroupDesc('');
      onSelectGroup(created);
      onNavigate('group_detail', { groupId: created.id });
    } catch (err: any) {
      Alert.alert('Error', err?.message || 'Failed to create group');
    } finally {
      setCreating(false);
    }
  };

  const handleAcceptInvite = async () => {
    if (!inviteToken.trim()) {
      Alert.alert('Validation Error', 'Please enter an invitation token.');
      return;
    }
    setAccepting(true);
    try {
      await acceptInvitation(inviteToken);
      Alert.alert('Success', 'You have joined the group!');
      setInviteModalVisible(false);
      setInviteToken('');
      fetchGroups();
    } catch (err: any) {
      Alert.alert('Error', err?.message || 'Invalid or expired invitation token');
    } finally {
      setAccepting(false);
    }
  };

  const getRoleBadgeColor = (role?: GroupRole) => {
    switch (role) {
      case 'OWNER':
        return { bg: '#FDEED9', text: '#B25E09' };
      case 'ADMIN':
        return { bg: '#E2E8F0', text: '#334155' };
      case 'CONTRIBUTOR':
        return { bg: '#EAF2EC', text: '#2D4A36' };
      case 'MEMBER':
        return { bg: '#EFF6FF', text: '#1D4ED8' };
      case 'GUEST':
      default:
        return { bg: '#F1F5F9', text: '#64748B' };
    }
  };

  const renderGroupItem = ({ item }: { item: Group }) => {
    const roleStyle = getRoleBadgeColor(item.my_role);
    return (
      <TouchableOpacity
        style={styles.groupCard}
        activeOpacity={0.85}
        onPress={() => {
          onSelectGroup(item);
          onNavigate('group_detail', { groupId: item.id });
        }}
      >
        <View style={styles.cardHeader}>
          <View style={styles.groupIconContainer}>
            <Ionicons name="people" size={22} color="#4A6B53" />
          </View>
          <View style={styles.titleArea}>
            <Text style={styles.groupName} numberOfLines={1}>
              {item.name}
            </Text>
            {item.description ? (
              <Text style={styles.groupDesc} numberOfLines={2}>
                {item.description}
              </Text>
            ) : null}
          </View>
          <View style={[styles.roleBadge, { backgroundColor: roleStyle.bg }]}>
            <Text style={[styles.roleBadgeText, { color: roleStyle.text }]}>
              {item.my_role || 'MEMBER'}
            </Text>
          </View>
        </View>

        <View style={styles.cardFooter}>
          <View style={styles.footerStat}>
            <Ionicons name="person-outline" size={14} color="#8B9E90" />
            <Text style={styles.footerStatText}>
              {item.member_count !== undefined ? `${item.member_count} members` : 'Active'}
            </Text>
          </View>
          <View style={styles.cardActionRow}>
            <Text style={styles.viewFeedText}>View Feed</Text>
            <Ionicons name="chevron-forward" size={16} color="#4A6B53" />
          </View>
        </View>
      </TouchableOpacity>
    );
  };

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <TouchableOpacity
            style={styles.backButton}
            onPress={() => onNavigate('home')}
            activeOpacity={0.8}
          >
            <Ionicons name="arrow-back" size={18} color="#4A6B53" />
            <Text style={styles.backButtonText}>Stream</Text>
          </TouchableOpacity>
          <View style={styles.headerTitleGroup}>
            <Text style={styles.headerTitle}>Groups</Text>
            <Text style={styles.headerSubtitle}>Collaborative memories</Text>
          </View>
        </View>
        <View style={styles.headerActions}>
          <TouchableOpacity
            style={styles.iconButton}
            onPress={() => setInviteModalVisible(true)}
            activeOpacity={0.8}
          >
            <Ionicons name="mail-outline" size={20} color="#4A6B53" />
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.createButton}
            onPress={() => setCreateModalVisible(true)}
            activeOpacity={0.85}
          >
            <Ionicons name="add" size={20} color="#FFFFFF" />
            <Text style={styles.createButtonText}>New Group</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Body */}
      {loading ? (
        <View style={styles.centerContainer}>
          <ActivityIndicator size="large" color="#4A6B53" />
          <Text style={styles.loadingText}>Loading groups...</Text>
        </View>
      ) : error ? (
        <View style={styles.centerContainer}>
          <Ionicons name="alert-circle-outline" size={40} color="#D9534F" />
          <Text style={styles.errorText}>{error}</Text>
          <TouchableOpacity style={styles.retryButton} onPress={fetchGroups}>
            <Text style={styles.retryButtonText}>Retry</Text>
          </TouchableOpacity>
        </View>
      ) : groups.length === 0 ? (
        <View style={styles.emptyContainer}>
          <View style={styles.emptyIconCircle}>
            <Ionicons name="people-outline" size={44} color="#4A6B53" />
          </View>
          <Text style={styles.emptyTitle}>No Groups Yet</Text>
          <Text style={styles.emptySubtitle}>
            Create a collaborative space or accept an invitation to share and search memories with your team.
          </Text>
          <TouchableOpacity
            style={styles.emptyActionBtn}
            onPress={() => setCreateModalVisible(true)}
            activeOpacity={0.85}
          >
            <Text style={styles.emptyActionBtnText}>Create Your First Group</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <FlatList
          data={groups}
          keyExtractor={(item) => item.id}
          renderItem={renderGroupItem}
          contentContainerStyle={styles.listContent}
          showsVerticalScrollIndicator={false}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={onRefresh}
              tintColor="#4A6B53"
              colors={['#4A6B53']}
            />
          }
        />
      )}

      {/* Create Group Modal */}
      <Modal visible={createModalVisible} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Create New Group</Text>
              <TouchableOpacity onPress={() => setCreateModalVisible(false)}>
                <Ionicons name="close" size={22} color="#1F2923" />
              </TouchableOpacity>
            </View>

            <Text style={styles.inputLabel}>Group Name</Text>
            <TextInput
              style={styles.input}
              placeholder="e.g. AI Research Team"
              placeholderTextColor="#8B9E90"
              value={newGroupName}
              onChangeText={setNewGroupName}
            />

            <Text style={styles.inputLabel}>Description (Optional)</Text>
            <TextInput
              style={[styles.input, styles.textArea]}
              placeholder="Shared notes, papers, and architectural memories"
              placeholderTextColor="#8B9E90"
              value={newGroupDesc}
              onChangeText={setNewGroupDesc}
              multiline
              numberOfLines={3}
            />

            <View style={styles.modalBtnRow}>
              <TouchableOpacity
                style={styles.cancelBtn}
                onPress={() => setCreateModalVisible(false)}
                disabled={creating}
              >
                <Text style={styles.cancelBtnText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.submitBtn}
                onPress={handleCreateGroup}
                disabled={creating}
              >
                {creating ? (
                  <ActivityIndicator size="small" color="#FFFFFF" />
                ) : (
                  <Text style={styles.submitBtnText}>Create Group</Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* Accept Invitation Modal */}
      <Modal visible={inviteModalVisible} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Join via Invitation Token</Text>
              <TouchableOpacity onPress={() => setInviteModalVisible(false)}>
                <Ionicons name="close" size={22} color="#1F2923" />
              </TouchableOpacity>
            </View>

            <Text style={styles.inputLabel}>Invitation Token</Text>
            <TextInput
              style={styles.input}
              placeholder="Paste invitation token from email/invite"
              placeholderTextColor="#8B9E90"
              value={inviteToken}
              onChangeText={setInviteToken}
              autoCapitalize="none"
            />

            <View style={styles.modalBtnRow}>
              <TouchableOpacity
                style={styles.cancelBtn}
                onPress={() => setInviteModalVisible(false)}
                disabled={accepting}
              >
                <Text style={styles.cancelBtnText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.submitBtn}
                onPress={handleAcceptInvite}
                disabled={accepting}
              >
                {accepting ? (
                  <ActivityIndicator size="small" color="#FFFFFF" />
                ) : (
                  <Text style={styles.submitBtnText}>Join Group</Text>
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
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingTop: 56,
    paddingBottom: 16,
    backgroundColor: '#FFFFFF',
    borderBottomWidth: 1,
    borderBottomColor: '#E2DDD2',
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    flex: 1,
  },
  backButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 10,
    backgroundColor: '#FAF7F0',
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
  },
  headerTitle: {
    fontSize: 22,
    fontWeight: '800',
    color: '#1F2923',
  },
  headerSubtitle: {
    fontSize: 11,
    color: '#5E7A64',
    marginTop: 1,
  },
  headerActions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  iconButton: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: '#FAF7F0',
    borderWidth: 1,
    borderColor: '#D5CDBC',
    alignItems: 'center',
    justifyContent: 'center',
  },
  createButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#4A6B53',
    paddingVertical: 9,
    paddingHorizontal: 14,
    borderRadius: 20,
    gap: 4,
  },
  createButtonText: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 13,
  },
  listContent: {
    padding: 16,
    paddingBottom: 100,
  },
  groupCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#E2DDD2',
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 6,
    elevation: 2,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 12,
  },
  groupIconContainer: {
    width: 44,
    height: 44,
    borderRadius: 12,
    backgroundColor: '#EAF2EC',
    alignItems: 'center',
    justifyContent: 'center',
  },
  titleArea: {
    flex: 1,
  },
  groupName: {
    fontSize: 16,
    fontWeight: '700',
    color: '#1F2923',
    marginBottom: 4,
  },
  groupDesc: {
    fontSize: 13,
    color: '#5E7A64',
    lineHeight: 18,
  },
  roleBadge: {
    paddingVertical: 4,
    paddingHorizontal: 8,
    borderRadius: 8,
  },
  roleBadgeText: {
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 0.5,
  },
  cardFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 14,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#F0ECE4',
  },
  footerStat: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  footerStatText: {
    fontSize: 12,
    color: '#8B9E90',
  },
  cardActionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  viewFeedText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#4A6B53',
  },
  centerContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 32,
  },
  loadingText: {
    marginTop: 12,
    fontSize: 14,
    color: '#5E7A64',
  },
  errorText: {
    marginTop: 12,
    fontSize: 14,
    color: '#D9534F',
    textAlign: 'center',
  },
  retryButton: {
    marginTop: 16,
    paddingVertical: 8,
    paddingHorizontal: 20,
    backgroundColor: '#4A6B53',
    borderRadius: 20,
  },
  retryButtonText: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 13,
  },
  emptyContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 40,
  },
  emptyIconCircle: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: '#EAF2EC',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 16,
  },
  emptyTitle: {
    fontSize: 18,
    fontWeight: '800',
    color: '#1F2923',
    marginBottom: 8,
  },
  emptySubtitle: {
    fontSize: 14,
    color: '#5E7A64',
    textAlign: 'center',
    lineHeight: 20,
    marginBottom: 24,
  },
  emptyActionBtn: {
    backgroundColor: '#4A6B53',
    paddingVertical: 12,
    paddingHorizontal: 24,
    borderRadius: 24,
  },
  emptyActionBtnText: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 14,
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
    padding: 24,
    paddingBottom: 40,
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 20,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: '800',
    color: '#1F2923',
  },
  inputLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: '#5E7A64',
    marginBottom: 6,
    marginTop: 12,
  },
  input: {
    backgroundColor: '#FAF7F0',
    borderWidth: 1,
    borderColor: '#D5CDBC',
    borderRadius: 12,
    padding: 12,
    fontSize: 14,
    color: '#1F2923',
  },
  textArea: {
    height: 80,
    textAlignVertical: 'top',
  },
  modalBtnRow: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 12,
    marginTop: 24,
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
