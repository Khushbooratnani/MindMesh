import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  SafeAreaView,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAuth } from '../auth/AuthContext';
import { ScreenId } from '../types';
import { FloatingBottomDock } from '../components/FloatingBottomDock';

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

  useEffect(() => {
    checkLocker();
  }, [checkLocker]);

  const handleAction = async () => {
    setLocalError('');
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
        await createLocker(password);
        setPassword('');
        setConfirmPassword('');
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

  const renderContent = () => {
    if (isLockerLoading) {
      return <ActivityIndicator size="large" color="#4A6B53" />;
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
            This cannot be recovered if lost.
          </Text>

          <TextInput
            style={styles.input}
            placeholder="Locker Password"
            secureTextEntry
            value={password}
            onChangeText={setPassword}
          />
          <TextInput
            style={styles.input}
            placeholder="Confirm Password"
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
      return (
        <View style={styles.formContainer}>
          <View style={styles.iconContainer}>
            <Ionicons name="lock-closed" size={64} color="#4A6B53" />
          </View>
          <Text style={styles.title}>Locker Locked</Text>
          <Text style={styles.subtitle}>Enter your password to access private memories.</Text>

          <TextInput
            style={styles.input}
            placeholder="Password"
            secureTextEntry
            value={password}
            onChangeText={setPassword}
          />

          {(error || localError) ? (
            <Text style={styles.errorText}>{error || localError}</Text>
          ) : null}

          <TouchableOpacity style={styles.button} onPress={handleAction}>
            <Text style={styles.buttonText}>Unlock</Text>
          </TouchableOpacity>
        </View>
      );
    }

    return (
      <View style={styles.formContainer}>
        <View style={styles.iconContainer}>
          <Ionicons name="lock-open" size={64} color="#D9534F" />
        </View>
        <Text style={styles.title}>Locker Unlocked</Text>
        <Text style={styles.subtitle}>
          Your private memories are now accessible across the app. 
          The locker will automatically lock after 120 seconds of inactivity.
        </Text>

        <TouchableOpacity style={[styles.button, styles.lockButton]} onPress={handleAction}>
          <Text style={styles.buttonText}>Lock Now</Text>
        </TouchableOpacity>
      </View>
    );
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.container}
      >
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
  content: {
    flex: 1,
    justifyContent: 'center',
    padding: 24,
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
  errorText: {
    color: '#D9534F',
    marginBottom: 16,
    textAlign: 'center',
  }
});
