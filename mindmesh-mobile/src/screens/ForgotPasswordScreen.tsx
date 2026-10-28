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

interface ForgotPasswordScreenProps {
  onNavigate: (id: ScreenId) => void;
}

export const ForgotPasswordScreen: React.FC<ForgotPasswordScreenProps> = ({ onNavigate }) => {
  const { resetPassword, isLoading, error, clearError } = useAuth();

  const [email, setEmail] = useState('');
  const [localError, setLocalError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const displayError = localError || error;

  const handleResetPassword = async () => {
    setLocalError(null);
    clearError();

    if (!email.trim()) {
      setLocalError('Please enter your email address.');
      return;
    }

    setIsSubmitting(true);
    try {
      const res = await resetPassword(email);
      setIsSubmitted(true);
      setSuccessMessage(res.message);
    } catch (err: any) {
      setLocalError(err.message || 'Unable to submit password reset request.');
    } finally {
      setIsSubmitting(false);
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
            <MindMeshLogo size="md" withText={true} />
            <Text style={styles.mainTitle}>Reset Your Password</Text>
            <Text style={styles.subtitle}>
              Enter the email address associated with your MindMesh vault and we will send you instructions to reset your password.
            </Text>
          </View>

          {/* Error Banner */}
          {displayError ? (
            <View style={styles.errorCard}>
              <Ionicons name="alert-circle" size={20} color="#D9534F" />
              <Text style={styles.errorText}>{displayError}</Text>
            </View>
          ) : null}

          {/* Success State */}
          {isSubmitted ? (
            <View style={styles.successCard}>
              <View style={styles.successIconCircle}>
                <Ionicons name="checkmark-circle" size={36} color="#4A6B53" />
              </View>
              <Text style={styles.successTitle}>Check Your Inbox</Text>
              <Text style={styles.successText}>
                {successMessage ||
                  `If an account exists for ${email.trim()}, instructions to reset your password have been sent.`}
              </Text>
              <TouchableOpacity
                style={styles.primaryButton}
                onPress={() => onNavigate('login')}
                activeOpacity={0.88}
              >
                <Text style={styles.primaryButtonText}>Return to Log In</Text>
                <Ionicons name="arrow-forward" size={18} color="#FFFFFF" />
              </TouchableOpacity>
            </View>
          ) : (
            /* Input Form */
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

              <TouchableOpacity
                style={[
                  styles.primaryButton,
                  (!email.trim() || isLoading || isSubmitting) && styles.primaryButtonDisabled,
                ]}
                onPress={handleResetPassword}
                disabled={!email.trim() || isLoading || isSubmitting}
                activeOpacity={0.88}
              >
                {isSubmitting || isLoading ? (
                  <ActivityIndicator size="small" color="#FFFFFF" />
                ) : (
                  <>
                    <Text style={styles.primaryButtonText}>Send Reset Link</Text>
                    <Ionicons name="paper-plane-outline" size={18} color="#FFFFFF" />
                  </>
                )}
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.backButton}
                onPress={() => onNavigate('login')}
                activeOpacity={0.7}
              >
                <Ionicons name="arrow-back" size={16} color="#5E7A64" />
                <Text style={styles.backButtonText}>Back to Log In</Text>
              </TouchableOpacity>
            </View>
          )}
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
  mainTitle: {
    fontSize: 22,
    fontWeight: '800',
    color: '#233529',
    marginTop: 16,
    letterSpacing: -0.4,
  },
  subtitle: {
    fontSize: 13,
    color: '#5E7A64',
    textAlign: 'center',
    marginTop: 8,
    lineHeight: 18,
    paddingHorizontal: 8,
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
  successCard: {
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#E5DFD5',
    borderRadius: 20,
    padding: 24,
    alignItems: 'center',
    gap: 12,
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 6,
    elevation: 2,
  },
  successIconCircle: {
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: '#EBF4ED',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 4,
  },
  successTitle: {
    fontSize: 18,
    fontWeight: '800',
    color: '#233529',
  },
  successText: {
    fontSize: 13,
    color: '#5E7A64',
    textAlign: 'center',
    lineHeight: 18,
    marginBottom: 8,
  },
  formGroup: {
    gap: 14,
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
  primaryButton: {
    backgroundColor: '#4A6B53',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 16,
    borderRadius: 20,
    gap: 8,
    marginTop: 4,
    shadowColor: '#4A6B53',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.25,
    shadowRadius: 8,
    elevation: 3,
    width: '100%',
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
  backButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 12,
    marginTop: 4,
  },
  backButtonText: {
    fontSize: 13,
    fontWeight: '700',
    color: '#5E7A64',
  },
});
