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

interface LoginScreenProps {
  onNavigate: (id: ScreenId) => void;
}

export const LoginScreen: React.FC<LoginScreenProps> = ({ onNavigate }) => {
  const { signIn, signInWithGoogle, signInWithApple, isLoading, error, clearError } = useAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const displayError = localError || error;

  const handleEmailLogin = async () => {
    setLocalError(null);
    clearError();

    if (!email.trim()) {
      setLocalError('Please enter your email address.');
      return;
    }
    if (!password) {
      setLocalError('Please enter your password.');
      return;
    }

    setIsSubmitting(true);
    try {
      await signIn({ email, password });
      onNavigate('home');
    } catch (err: any) {
      setLocalError(err.message || 'Login failed. Please verify your credentials.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleGoogleLogin = async () => {
    setLocalError(null);
    clearError();
    try {
      await signInWithGoogle();
      onNavigate('home');
    } catch (err: any) {
      setLocalError(err.message || 'Google Sign-In is unavailable.');
    }
  };

  const handleAppleLogin = async () => {
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
            <MindMeshLogo size="xl" withText={true} />
            <Text style={styles.tagline}>Your memories, connected.</Text>
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
              onPress={handleGoogleLogin}
              disabled={isLoading || isSubmitting}
              activeOpacity={0.85}
            >
              <Ionicons name="logo-google" size={18} color="#233529" />
              <Text style={styles.socialButtonText}>Continue with Google</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.socialButton}
              onPress={handleAppleLogin}
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
            <Text style={styles.dividerText}>or continue with email</Text>
            <View style={styles.dividerLine} />
          </View>

          {/* Email / Password Form */}
          <View style={styles.formGroup}>
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
                placeholder="Password"
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

            {/* Forgot Password Link */}
            <TouchableOpacity
              style={styles.forgotBtn}
              onPress={() => onNavigate('forgot_password')}
              activeOpacity={0.7}
            >
              <Text style={styles.forgotText}>Forgot password?</Text>
            </TouchableOpacity>

            {/* Submit Button */}
            <TouchableOpacity
              style={[
                styles.primaryButton,
                (!email.trim() || !password || isLoading || isSubmitting) &&
                  styles.primaryButtonDisabled,
              ]}
              onPress={handleEmailLogin}
              disabled={!email.trim() || !password || isLoading || isSubmitting}
              activeOpacity={0.88}
            >
              {isSubmitting || isLoading ? (
                <ActivityIndicator size="small" color="#FFFFFF" />
              ) : (
                <>
                  <Text style={styles.primaryButtonText}>Log In</Text>
                  <Ionicons name="arrow-forward" size={18} color="#FFFFFF" />
                </>
              )}
            </TouchableOpacity>
          </View>

          {/* Switch to Sign Up */}
          <View style={styles.footer}>
            <Text style={styles.footerText}>Don't have an account?</Text>
            <TouchableOpacity
              onPress={() => {
                clearError();
                setLocalError(null);
                onNavigate('signup');
              }}
              activeOpacity={0.7}
            >
              <Text style={styles.footerLink}> Sign Up</Text>
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
    marginBottom: 24,
  },
  tagline: {
    fontSize: 14,
    fontWeight: '600',
    color: '#5E7A64',
    marginTop: 8,
    letterSpacing: 0.2,
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
    marginBottom: 18,
  },
  socialButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#D5CDBC',
    borderRadius: 18,
    paddingVertical: 14,
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
    marginVertical: 14,
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
    gap: 12,
  },
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#D5CDBC',
    borderRadius: 18,
    paddingHorizontal: 14,
    paddingVertical: 4,
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
  forgotBtn: {
    alignSelf: 'flex-end',
    paddingVertical: 4,
  },
  forgotText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#4A6B53',
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
    marginTop: 24,
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
