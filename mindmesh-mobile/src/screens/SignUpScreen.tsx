import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { MindMeshLogo } from '../components/MindMeshLogo';
import { ScreenId } from '../types';
import { useAuth } from '../auth/AuthContext';

interface SignUpScreenProps {
  onNavigate: (id: ScreenId) => void;
}

export const SignUpScreen: React.FC<SignUpScreenProps> = ({ onNavigate }) => {
  const { signUp, signInWithGoogle, signInWithApple, isLoading, error, clearError } = useAuth();

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const displayError = localError || error;

  const handleSignUp = async () => {
    setLocalError(null);
    clearError();

    if (!name.trim()) {
      setLocalError('Please enter your full name.');
      return;
    }
    if (!email.trim()) {
      setLocalError('Please enter your email address.');
      return;
    }
    if (!password) {
      setLocalError('Please create a password.');
      return;
    }
    if (password.length < 8) {
      setLocalError('Password must be at least 8 characters long.');
      return;
    }
    if (password !== confirmPassword) {
      setLocalError('Passwords do not match. Please verify your password.');
      return;
    }

    setIsSubmitting(true);
    try {
      await signUp({ name, email, password, confirmPassword });
      onNavigate('home');
    } catch (err: any) {
      setLocalError(err.message || 'Account creation failed. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleGoogleSignUp = async () => {
    setLocalError(null);
    clearError();
    try {
      await signInWithGoogle();
      onNavigate('home');
    } catch (err: any) {
      setLocalError(err.message || 'Google Sign-In is unavailable.');
    }
  };

  const handleAppleSignUp = async () => {
    setLocalError(null);
    clearError();
    try {
      await signInWithApple();
      onNavigate('home');
    } catch (err: any) {
      setLocalError(err.message || 'Apple Sign-In is unavailable.');
    }
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.container}
      >
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
        >
          {/* Header & Logo */}
          <View style={styles.header}>
            <MindMeshLogo size="lg" withText={true} />
            <Text style={styles.mainTitle}>Create Your Mind Vault</Text>
            <Text style={styles.tagline}>
              Sovereign multimodal memory intelligence.
            </Text>
          </View>

          {/* Error Banner */}
          {displayError ? (
            <View style={styles.errorCard}>
              <Ionicons name="alert-circle" size={20} color="#D9534F" />
              <Text style={styles.errorText}>{displayError}</Text>
            </View>
          ) : null}

          {/* Social Auth Buttons */}
          <View style={styles.socialGroup}>
            <TouchableOpacity
              style={styles.socialButton}
              onPress={handleGoogleSignUp}
              disabled={isLoading || isSubmitting}
              activeOpacity={0.85}
            >
              <Ionicons name="logo-google" size={18} color="#233529" />
              <Text style={styles.socialButtonText}>Continue with Google</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.socialButton}
              onPress={handleAppleSignUp}
              disabled={isLoading || isSubmitting}
              activeOpacity={0.85}
            >
              <Ionicons name="logo-apple" size={20} color="#233529" />
              <Text style={styles.socialButtonText}>Continue with Apple</Text>
            </TouchableOpacity>
          </View>

          {/* Divider */}
          <View style={styles.dividerRow}>
            <View style={styles.dividerLine} />
            <Text style={styles.dividerText}>or register with email</Text>
            <View style={styles.dividerLine} />
          </View>

          {/* Form Group */}
          <View style={styles.formGroup}>
            <View style={styles.inputContainer}>
              <Ionicons name="person-outline" size={18} color="#5E7A64" style={styles.inputIcon} />
              <TextInput
                style={styles.input}
                placeholder="Full Name"
                placeholderTextColor="#8A9E8F"
                value={name}
                onChangeText={(text) => {
                  setName(text);
                  if (localError) setLocalError(null);
                }}
                editable={!isLoading && !isSubmitting}
              />
            </View>

            <View style={styles.inputContainer}>
              <Ionicons name="mail-outline" size={18} color="#5E7A64" style={styles.inputIcon} />
              <TextInput
                style={styles.input}
                placeholder="Email address"
                placeholderTextColor="#8A9E8F"
                value={email}
                onChangeText={(text) => {
                  setEmail(text);
                  if (localError) setLocalError(null);
                }}
                autoCapitalize="none"
                keyboardType="email-address"
                autoComplete="email"
                editable={!isLoading && !isSubmitting}
              />
            </View>

            <View style={styles.inputContainer}>
              <Ionicons name="lock-closed-outline" size={18} color="#5E7A64" style={styles.inputIcon} />
              <TextInput
                style={styles.input}
                placeholder="Password (min. 8 characters)"
                placeholderTextColor="#8A9E8F"
                value={password}
                onChangeText={(text) => {
                  setPassword(text);
                  if (localError) setLocalError(null);
                }}
                secureTextEntry={!showPassword}
                autoCapitalize="none"
                editable={!isLoading && !isSubmitting}
              />
              <TouchableOpacity
                onPress={() => setShowPassword((prev) => !prev)}
                style={styles.eyeBtn}
                activeOpacity={0.7}
              >
                <Ionicons
                  name={showPassword ? 'eye-off-outline' : 'eye-outline'}
                  size={18}
                  color="#5E7A64"
                />
              </TouchableOpacity>
            </View>

            <View style={styles.inputContainer}>
              <Ionicons name="shield-checkmark-outline" size={18} color="#5E7A64" style={styles.inputIcon} />
              <TextInput
                style={styles.input}
                placeholder="Confirm Password"
                placeholderTextColor="#8A9E8F"
                value={confirmPassword}
                onChangeText={(text) => {
                  setConfirmPassword(text);
                  if (localError) setLocalError(null);
                }}
                secureTextEntry={!showPassword}
                autoCapitalize="none"
                editable={!isLoading && !isSubmitting}
              />
            </View>

            {/* Submit Button */}
            <TouchableOpacity
              style={[
                styles.primaryButton,
                (!name.trim() || !email.trim() || !password || isLoading || isSubmitting) &&
                  styles.primaryButtonDisabled,
              ]}
              onPress={handleSignUp}
              disabled={!name.trim() || !email.trim() || !password || isLoading || isSubmitting}
              activeOpacity={0.88}
            >
              {isSubmitting || isLoading ? (
                <ActivityIndicator size="small" color="#FFFFFF" />
              ) : (
                <>
                  <Text style={styles.primaryButtonText}>Create Account</Text>
                  <Ionicons name="arrow-forward" size={18} color="#FFFFFF" />
                </>
              )}
            </TouchableOpacity>
          </View>

          {/* Switch to Login */}
          <View style={styles.footer}>
            <Text style={styles.footerText}>Already have an account?</Text>
            <TouchableOpacity
              onPress={() => {
                clearError();
                setLocalError(null);
                onNavigate('login');
              }}
              activeOpacity={0.7}
            >
              <Text style={styles.footerLink}> Log In</Text>
            </TouchableOpacity>
          </View>
        </ScrollView>
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
  },
  scrollContent: {
    paddingHorizontal: 24,
    paddingVertical: 20,
    justifyContent: 'center',
    minHeight: '100%',
  },
  header: {
    alignItems: 'center',
    marginBottom: 20,
  },
  mainTitle: {
    fontSize: 20,
    fontWeight: '800',
    color: '#233529',
    marginTop: 12,
    letterSpacing: -0.4,
  },
  tagline: {
    fontSize: 12,
    fontWeight: '600',
    color: '#5E7A64',
    marginTop: 4,
  },
  errorCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FDF2F2',
    borderWidth: 1,
    borderColor: '#F5C6CB',
    borderRadius: 16,
    padding: 12,
    gap: 10,
    marginBottom: 16,
  },
  errorText: {
    flex: 1,
    fontSize: 12,
    fontWeight: '600',
    color: '#D9534F',
    lineHeight: 16,
  },
  socialGroup: {
    gap: 10,
    marginBottom: 16,
  },
  socialButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#D5CDBC',
    borderRadius: 18,
    paddingVertical: 13,
    gap: 10,
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 4,
    elevation: 1,
  },
  socialButtonText: {
    fontSize: 14,
    fontWeight: '700',
    color: '#233529',
  },
  dividerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginVertical: 12,
  },
  dividerLine: {
    flex: 1,
    height: 1,
    backgroundColor: '#E5DFD5',
  },
  dividerText: {
    fontSize: 11,
    fontWeight: '600',
    color: '#8A9E8F',
    marginHorizontal: 12,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  formGroup: {
    gap: 10,
  },
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#D5CDBC',
    borderRadius: 18,
    paddingHorizontal: 14,
    paddingVertical: 3,
  },
  inputIcon: {
    marginRight: 10,
  },
  input: {
    flex: 1,
    fontSize: 14,
    color: '#233529',
    paddingVertical: 12,
  },
  eyeBtn: {
    padding: 6,
  },
  primaryButton: {
    backgroundColor: '#4A6B53',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 16,
    borderRadius: 20,
    gap: 8,
    marginTop: 6,
    shadowColor: '#4A6B53',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.25,
    shadowRadius: 8,
    elevation: 3,
  },
  primaryButtonDisabled: {
    backgroundColor: '#A8BCAD',
    shadowOpacity: 0.05,
  },
  primaryButtonText: {
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: '700',
    letterSpacing: 0.3,
  },
  footer: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 20,
    paddingBottom: 16,
  },
  footerText: {
    fontSize: 13,
    color: '#5E7A64',
    fontWeight: '500',
  },
  footerLink: {
    fontSize: 13,
    color: '#4A6B53',
    fontWeight: '700',
  },
});
