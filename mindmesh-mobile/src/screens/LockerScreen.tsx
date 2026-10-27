import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  Alert,
  Image,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useAuth } from '../auth/AuthContext';
import { ScreenId } from '../types';
import { FloatingBottomDock } from '../components/FloatingBottomDock';
import {
  getLockerMemories,
  recoverLockerPassword,
  changeLockerPassword,
} from '../services/apiClient';
import { localFirstAdapter } from '../local_first/localFirstAdapter';

interface LockerProps {
  onNavigate: (id: ScreenId) => void;
}

export const LockerScreen: React.FC<LockerProps> = ({ onNavigate }) => {
  const {
    lockerExists,
    isLockerUnlocked,
    isLockerLoading,
    error,
    clearError,
    checkLocker,
    createLocker,
    unlockLocker,
    lockLocker,
  } = useAuth();

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [localError, setLocalError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  // Private memory state
  const [memories, setMemories] = useState<any[]>([]);
  const [allMemories, setAllMemories] = useState<any[]>([]);
  const [loadingMemories, setLoadingMemories] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  // Recovery state
  const [isRecoveryMode, setIsRecoveryMode] = useState(false);
  const [recoveryKey, setRecoveryKey] = useState('');
  const [newRecoveryPassword, setNewRecoveryPassword] = useState('');

  // Change password state
  const [showChangePassword, setShowChangePassword] = useState(false);
  const [oldPassword, setOldPassword] = useState('');
  const [newPasswordVal, setNewPasswordVal] = useState('');

  useEffect(() => {
    checkLocker();
  }, [checkLocker]);

  // Load private memories whenever the locker is unlocked
  const loadPrivateMemories = useCallback(async () => {
    if (!isLockerUnlocked) return;
    setLoadingMemories(true);
    setLocalError('');
    try {
      // 1. Load phone-local encrypted memories (PATH A: Device-Only persistence)
      let localItems: any[] = [];
      try {
        const localMems = await localFirstAdapter.listPrivateMemories();
        localItems = localMems.map((m) => ({
          id: m.id,
          raw_payload: m.text,
          media_type: m.mediaUri ? 'image' : 'text',
          media_uri: m.mediaUri,
          received_at: m.createdAt,
          user_context: m.title ? `Title: ${m.title}` : undefined,
          is_local_first: true,
        }));
      } catch (localErr) {
        console.warn('[LockerScreen] Could not read local encrypted vault:', localErr);
      }

      // 2. Load legacy server private memories (Package A fallback)
      let legacyItems: any[] = [];
      try {
        const data = await getLockerMemories();
        legacyItems = (data.items || []).map((item: any) => ({
          ...item,
          is_local_first: false,
        }));
      } catch (legacyErr: any) {
        console.warn('[LockerScreen] Legacy server locker unavailable:', legacyErr);
      }

      const merged = [...localItems, ...legacyItems];
      setAllMemories(merged);
      setMemories(merged);
    } catch (e: any) {
      if (e.message && (e.message.includes('401') || e.message.includes('403') || e.message.includes('timeout'))) {
        await lockLocker();
        setLocalError('Locker session expired. Please unlock again.');
      } else {
        setLocalError(e.message || 'Failed to load private memories');
      }
    } finally {
      setLoadingMemories(false);
    }
  }, [isLockerUnlocked, lockLocker]);

  // Filter memories locally when searchQuery changes
  useEffect(() => {
    if (!searchQuery.trim()) {
      setMemories(allMemories);
      return;
    }
    const q = searchQuery.toLowerCase();
    const filtered = allMemories.filter((m) => {
      const textMatch = (m.raw_payload || '').toLowerCase().includes(q);
      const ctxMatch = (m.user_context || '').toLowerCase().includes(q);
      return textMatch || ctxMatch;
    });
    setMemories(filtered);
  }, [searchQuery, allMemories]);

  useEffect(() => {
    if (isLockerUnlocked) {
      loadPrivateMemories();
    } else {
      setMemories([]);
      setAllMemories([]);
      setSearchQuery('');
    }
  }, [isLockerUnlocked, loadPrivateMemories]);

  const handleAction = async () => {
    setLocalError('');
    setSuccessMessage('');
    clearError();

    try {
      if (!lockerExists) {
        if (!password || password.length < 8) {
          setLocalError('Password must be at least 8 characters');
          return;
        }
        if (password !== confirmPassword) {
          setLocalError('Passwords do not match');
          return;
        }
        const res = await createLocker(password);
        setPassword('');
        setConfirmPassword('');
        const key = (res as any)?.recoveryKey;
        if (key) {
          Alert.alert(
            'Locker Initialized',
            `IMPORTANT: Save your recovery key securely. If you ever forget your locker password, this is the only way to restore access:\n\n${key}`,
            [{ text: 'I Have Saved It' }]
          );
        }
      } else if (!isLockerUnlocked) {
        if (!password) {
          setLocalError('Please enter password');
          return;
        }
        await unlockLocker(password);
        setPassword('');
      } else {
        await lockLocker();
      }
    } catch (e: any) {
      setLocalError(e.message || 'Operation failed');
    }
  };

  const handleRecover = async () => {
    setLocalError('');
    setSuccessMessage('');
    if (!recoveryKey.trim() || !newRecoveryPassword.trim()) {
      setLocalError('Please fill in both your recovery key and new password');
      return;
    }
    if (newRecoveryPassword.length < 8) {
      setLocalError('New password must be at least 8 characters');
      return;
    }

    try {
      const res = await recoverLockerPassword(recoveryKey.trim(), newRecoveryPassword.trim());
      setIsRecoveryMode(false);
      setRecoveryKey('');
      setNewRecoveryPassword('');
      Alert.alert(
        'Password Recovered',
        `Your password has been reset! A new rotated recovery key has been generated:\n\n${res.new_recovery_key}\n\nPlease store this new key in a safe place. Your old key is now invalidated.`,
        [{ text: 'OK' }]
      );
      setSuccessMessage('Password recovered successfully. You may now unlock.');
    } catch (e: any) {
      setLocalError(e.message || 'Recovery failed. Check your recovery key.');
    }
  };

  const handleChangePassword = async () => {
    setLocalError('');
    setSuccessMessage('');
    if (!oldPassword || !newPasswordVal) {
      setLocalError('Please enter both current and new passwords');
      return;
    }
    if (newPasswordVal.length < 8) {
      setLocalError('New password must be at least 8 characters');
      return;
    }

    try {
      await changeLockerPassword(oldPassword, newPasswordVal);
      setOldPassword('');
      setNewPasswordVal('');
      setShowChangePassword(false);
      Alert.alert('Success', 'Locker password changed successfully. All previous locker sessions have been revoked.');
      setSuccessMessage('Password changed successfully.');
    } catch (e: any) {
      setLocalError(e.message || 'Failed to change password. Verify your current password.');
    }
  };

  const renderContent = () => {
    if (isLockerLoading) {
      return (
        <View style={styles.centerContainer}>
          <ActivityIndicator size="large" color="#4A6B53" />
        </View>
      );
    }

    if (!lockerExists) {
      return (
        <View style={styles.formContainer}>
          <View style={styles.iconContainer}>
            <Ionicons name="shield-checkmark" size={64} color="#4A6B53" />
          </View>
          <Text style={styles.title}>Create Private Locker</Text>
          <Text style={styles.subtitle}>
            Secure your sensitive memories. Set a password that only you know.
            A recovery key will be generated for emergency access.
          </Text>

          <TextInput
            style={styles.input}
            placeholder="Locker Password (min 8 chars)"
            placeholderTextColor="#999"
            secureTextEntry
            value={password}
            onChangeText={setPassword}
          />
          <TextInput
            style={styles.input}
            placeholder="Confirm Password"
            placeholderTextColor="#999"
            secureTextEntry
            value={confirmPassword}
            onChangeText={setConfirmPassword}
          />

          {(error || localError) ? (
            <Text style={styles.errorText}>{error || localError}</Text>
          ) : null}

          <TouchableOpacity style={styles.button} onPress={handleAction}>
            <Text style={styles.buttonText}>Initialize Locker</Text>
          </TouchableOpacity>
        </View>
      );
    }

    if (!isLockerUnlocked) {
      if (isRecoveryMode) {
        return (
          <View style={styles.formContainer}>
            <View style={styles.iconContainer}>
              <Ionicons name="key" size={56} color="#D97706" />
            </View>
            <Text style={styles.title}>Recover Locker</Text>
            <Text style={styles.subtitle}>
              Enter your 32-character recovery key to reset your locker password.
            </Text>

            <TextInput
              style={styles.input}
              placeholder="Recovery Key"
              placeholderTextColor="#999"
              autoCapitalize="none"
              value={recoveryKey}
              onChangeText={setRecoveryKey}
            />
            <TextInput
              style={styles.input}
              placeholder="New Locker Password"
              placeholderTextColor="#999"
              secureTextEntry
              value={newRecoveryPassword}
              onChangeText={setNewRecoveryPassword}
            />

            {(error || localError) ? (
              <Text style={styles.errorText}>{error || localError}</Text>
            ) : null}

            <TouchableOpacity style={styles.button} onPress={handleRecover}>
              <Text style={styles.buttonText}>Reset Password</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.textButton}
              onPress={() => {
                setIsRecoveryMode(false);
                setLocalError('');
              }}
            >
              <Text style={styles.textButtonText}>Back to Unlock</Text>
            </TouchableOpacity>
          </View>
        );
      }

      return (
        <View style={styles.formContainer}>
          <View style={styles.iconContainer}>
            <Ionicons name="lock-closed" size={64} color="#4A6B53" />
          </View>
          <Text style={styles.title}>Locker Locked</Text>
          <Text style={styles.subtitle}>Enter your password to access your private memories.</Text>

          <TextInput
            style={styles.input}
            placeholder="Password"
            placeholderTextColor="#999"
            secureTextEntry
            value={password}
            onChangeText={setPassword}
          />

          {(error || localError) ? (
            <Text style={styles.errorText}>{error || localError}</Text>
          ) : null}
          {successMessage ? (
            <Text style={styles.successText}>{successMessage}</Text>
          ) : null}

          <TouchableOpacity style={styles.button} onPress={handleAction}>
            <Text style={styles.buttonText}>Unlock</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.textButton}
            onPress={() => {
              setIsRecoveryMode(true);
              setLocalError('');
              setSuccessMessage('');
            }}
          >
            <Text style={styles.textButtonText}>Forgot Password? Use Recovery Key</Text>
          </TouchableOpacity>
        </View>
      );
    }

    // UNLOCKED STATE
    return (
      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        {/* Unlocked Banner */}
        <View style={styles.statusCard}>
          <View style={styles.statusRow}>
            <Ionicons name="lock-open" size={28} color="#2D5A27" />
            <View style={styles.statusTextContainer}>
              <Text style={styles.statusTitle}>Private Locker Active</Text>
              <Text style={styles.statusSubtitle}>
                Protected memories are visible. Auto-locks after 120s of inactivity.
              </Text>
            </View>
          </View>

          <View style={styles.actionRow}>
            <TouchableOpacity style={[styles.smallButton, styles.lockButton]} onPress={handleAction}>
              <Ionicons name="lock-closed-outline" size={16} color="#FFF" style={{ marginRight: 6 }} />
              <Text style={styles.buttonText}>Lock Now</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.smallButton, styles.captureButton]}
              onPress={() => onNavigate('composer')}
            >
              <Ionicons name="add-circle-outline" size={16} color="#FFF" style={{ marginRight: 6 }} />
              <Text style={styles.buttonText}>Add Memory</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.smallButton, styles.secondaryButton]}
              onPress={() => setShowChangePassword(!showChangePassword)}
            >
              <Ionicons name="key-outline" size={16} color="#4A6B53" style={{ marginRight: 6 }} />
              <Text style={styles.secondaryButtonText}>
                {showChangePassword ? 'Cancel' : 'Change Password'}
              </Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Change Password Dropdown */}
        {showChangePassword && (
          <View style={styles.changePasswordCard}>
            <Text style={styles.sectionTitle}>Change Locker Password</Text>
            <TextInput
              style={styles.input}
              placeholder="Current Password"
              placeholderTextColor="#999"
              secureTextEntry
              value={oldPassword}
              onChangeText={setOldPassword}
            />
            <TextInput
              style={styles.input}
              placeholder="New Password (min 8 chars)"
              placeholderTextColor="#999"
              secureTextEntry
              value={newPasswordVal}
              onChangeText={setNewPasswordVal}
            />
            <TouchableOpacity style={styles.button} onPress={handleChangePassword}>
              <Text style={styles.buttonText}>Update Password</Text>
            </TouchableOpacity>
          </View>
        )}

        {(error || localError) ? (
          <Text style={styles.errorText}>{error || localError}</Text>
        ) : null}
        {successMessage ? (
          <Text style={styles.successText}>{successMessage}</Text>
        ) : null}

        {/* Private Memory Section */}
        <View style={styles.memoriesHeaderRow}>
          <Text style={styles.memoriesTitle}>
            Private Memories ({memories.length})
          </Text>
          <TouchableOpacity onPress={loadPrivateMemories} disabled={loadingMemories}>
            <Ionicons
              name="refresh-outline"
              size={20}
              color={loadingMemories ? '#999' : '#4A6B53'}
            />
          </TouchableOpacity>
        </View>

        {/* Private Search Bar */}
        <View style={styles.searchBarContainer}>
          <Ionicons name="search" size={16} color="#718096" style={{ marginRight: 8 }} />
          <TextInput
            style={styles.searchBarInput}
            placeholder="Search private memories locally..."
            placeholderTextColor="#A0AEC0"
            value={searchQuery}
            onChangeText={setSearchQuery}
            clearButtonMode="while-editing"
          />
          {searchQuery ? (
            <TouchableOpacity onPress={() => setSearchQuery('')}>
              <Ionicons name="close-circle" size={16} color="#A0AEC0" />
            </TouchableOpacity>
          ) : null}
        </View>

        {loadingMemories ? (
          <View style={styles.loadingBox}>
            <ActivityIndicator size="small" color="#4A6B53" />
            <Text style={styles.loadingText}>Decrypting private memories...</Text>
          </View>
        ) : memories.length === 0 ? (
          <View style={styles.emptyCard}>
            <Ionicons name="folder-open-outline" size={48} color="#A0AEC0" />
            <Text style={styles.emptyTitle}>
              {searchQuery ? 'No Matching Private Memories' : 'No Private Memories Yet'}
            </Text>
            <Text style={styles.emptySubtitle}>
              {searchQuery
                ? 'Try a different search query for your local locker memories.'
                : 'Memories saved to Private Locker are encrypted and stored only on this device.'}
            </Text>
          </View>
        ) : (
          memories.map((item, index) => {
            const dateStr = item.received_at
              ? new Date(item.received_at).toLocaleDateString('en-US', {
                  month: 'short',
                  day: 'numeric',
                  hour: '2-digit',
                  minute: '2-digit',
                })
              : 'Recently added';

            return (
              <View key={item.id || index} style={styles.memoryCard}>
                <View style={styles.cardHeader}>
                  <View style={styles.badgeRow}>
                    <View style={item.is_local_first ? styles.deviceBadge : styles.privateBadge}>
                      <Ionicons
                        name={item.is_local_first ? 'phone-portrait-outline' : 'shield'}
                        size={12}
                        color={item.is_local_first ? '#1D4ED8' : '#4A6B53'}
                      />
                      <Text style={item.is_local_first ? styles.deviceBadgeText : styles.badgeText}>
                        {item.is_local_first ? 'On-Device' : 'Server Vault'}
                      </Text>
                    </View>
                    <Text style={styles.mediaTypeBadge}>{item.media_type?.toUpperCase()}</Text>
                  </View>
                  <Text style={styles.cardDate}>{dateStr}</Text>
                </View>

                {item.media_uri ? (
                  <View style={styles.imageContainer}>
                    <Image
                      source={{ uri: item.media_uri }}
                      style={styles.memoryImage}
                      resizeMode="cover"
                    />
                  </View>
                ) : null}

                <Text style={styles.cardContent} numberOfLines={4}>
                  {item.raw_payload || '[No Text Content]'}
                </Text>

                {item.user_context ? (
                  <View style={styles.contextRow}>
                    <Ionicons name="person-circle-outline" size={14} color="#666" />
                    <Text style={styles.contextText}>{item.user_context}</Text>
                  </View>
                ) : null}
              </View>
            );
          })
        )}
      </ScrollView>
    );
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.container}
      >
        {/* Top Header with Back to Stream button */}
        <View style={styles.topHeader}>
          <TouchableOpacity
            style={styles.backButton}
            onPress={() => onNavigate('home')}
            activeOpacity={0.8}
          >
            <Ionicons name="arrow-back" size={18} color="#4A6B53" />
            <Text style={styles.backButtonText}>Stream</Text>
          </TouchableOpacity>
          <View style={styles.headerTitleGroup}>
            <Text style={styles.headerMainTitle}>Private Locker</Text>
            <Text style={styles.headerSubtitleText}>Zero-Knowledge Encrypted</Text>
          </View>
        </View>

        <View style={styles.content}>
          {renderContent()}
        </View>
        <FloatingBottomDock activeScreenId="locker" onNavigate={onNavigate} />
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: '#FAF7F0' },
  container: { flex: 1 },
  topHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#E5DFD5',
  },
  backButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingVertical: 6,
    paddingHorizontal: 10,
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
    marginLeft: 12,
  },
  headerMainTitle: {
    fontSize: 17,
    fontWeight: '800',
    color: '#233529',
  },
  headerSubtitleText: {
    fontSize: 11,
    color: '#5E7A64',
  },
  content: {
    flex: 1,
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 80,
  },
  captureButton: {
    backgroundColor: '#4A6B53',
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  scrollContent: {
    paddingBottom: 24,
  },
  formContainer: {
    backgroundColor: '#FFFFFF',
    padding: 24,
    borderRadius: 16,
    shadowColor: '#000',
    shadowOpacity: 0.05,
    shadowRadius: 10,
    elevation: 2,
    alignItems: 'center',
    marginTop: 40,
  },
  iconContainer: {
    marginBottom: 16,
  },
  title: {
    fontSize: 22,
    fontWeight: '700',
    color: '#233529',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 14,
    color: '#5E7A64',
    textAlign: 'center',
    marginBottom: 24,
    lineHeight: 20,
  },
  input: {
    width: '100%',
    backgroundColor: '#F5F5F5',
    borderWidth: 1,
    borderColor: '#E0E0E0',
    borderRadius: 12,
    padding: 16,
    marginBottom: 16,
    fontSize: 16,
    color: '#233529',
  },
  button: {
    width: '100%',
    backgroundColor: '#4A6B53',
    padding: 16,
    borderRadius: 12,
    alignItems: 'center',
    marginTop: 8,
  },
  lockButton: {
    backgroundColor: '#D9534F',
  },
  buttonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },
  textButton: {
    marginTop: 16,
    padding: 8,
  },
  textButtonText: {
    color: '#4A6B53',
    fontSize: 14,
    fontWeight: '500',
  },
  errorText: {
    color: '#D9534F',
    marginVertical: 12,
    textAlign: 'center',
    fontSize: 14,
  },
  successText: {
    color: '#2D5A27',
    marginVertical: 12,
    textAlign: 'center',
    fontSize: 14,
    fontWeight: '500',
  },
  statusCard: {
    backgroundColor: '#E8F5E9',
    borderWidth: 1,
    borderColor: '#C8E6C9',
    borderRadius: 16,
    padding: 18,
    marginBottom: 16,
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 14,
  },
  statusTextContainer: {
    marginLeft: 12,
    flex: 1,
  },
  statusTitle: {
    fontSize: 17,
    fontWeight: '700',
    color: '#1B5E20',
  },
  statusSubtitle: {
    fontSize: 12,
    color: '#2E7D32',
    marginTop: 2,
  },
  actionRow: {
    flexDirection: 'row',
    gap: 12,
  },
  smallButton: {
    flex: 1,
    flexDirection: 'row',
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  secondaryButton: {
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#4A6B53',
  },
  secondaryButtonText: {
    color: '#4A6B53',
    fontSize: 14,
    fontWeight: '600',
  },
  changePasswordCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    padding: 16,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#E0E0E0',
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#233529',
    marginBottom: 12,
  },
  memoriesHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginVertical: 12,
  },
  memoriesTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#233529',
  },
  loadingBox: {
    alignItems: 'center',
    paddingVertical: 24,
  },
  loadingText: {
    marginTop: 8,
    color: '#5E7A64',
    fontSize: 13,
  },
  emptyCard: {
    backgroundColor: '#FFFFFF',
    padding: 32,
    borderRadius: 16,
    alignItems: 'center',
    marginVertical: 8,
    borderWidth: 1,
    borderColor: '#E2E8F0',
  },
  emptyTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#4A5568',
    marginTop: 12,
    marginBottom: 6,
  },
  emptySubtitle: {
    fontSize: 13,
    color: '#718096',
    textAlign: 'center',
    lineHeight: 18,
  },
  memoryCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 14,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    shadowColor: '#000',
    shadowOpacity: 0.03,
    shadowRadius: 6,
    elevation: 1,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  badgeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  privateBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#E8F5E9',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
    gap: 4,
  },
  badgeText: {
    fontSize: 11,
    fontWeight: '600',
    color: '#4A6B53',
  },
  mediaTypeBadge: {
    fontSize: 10,
    fontWeight: '700',
    color: '#718096',
    backgroundColor: '#EDF2F7',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  cardDate: {
    fontSize: 12,
    color: '#A0AEC0',
  },
  cardContent: {
    fontSize: 15,
    color: '#2D3748',
    lineHeight: 22,
  },
  contextRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 10,
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: '#F7FAFC',
    gap: 6,
  },
  contextText: {
    fontSize: 12,
    color: '#718096',
    fontStyle: 'italic',
  },
  searchBarContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 8,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#E2E8F0',
  },
  searchBarInput: {
    flex: 1,
    fontSize: 14,
    color: '#2D3748',
    padding: 0,
  },
  deviceBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#EFF6FF',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
    gap: 4,
    borderWidth: 1,
    borderColor: '#DBEAFE',
  },
  deviceBadgeText: {
    fontSize: 11,
    fontWeight: '600',
    color: '#1D4ED8',
  },
  imageContainer: {
    borderRadius: 10,
    overflow: 'hidden',
    marginVertical: 10,
    backgroundColor: '#000',
  },
  memoryImage: {
    width: '100%',
    height: 200,
    borderRadius: 10,
  },
});
