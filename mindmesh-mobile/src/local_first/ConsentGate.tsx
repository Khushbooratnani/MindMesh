/**
 * Reusable Consent Gate Modal Component.
 *
 * STRICT PRIVACY REQUIREMENTS:
 * - Content selected is explicitly displayed to the user.
 * - Purpose of processing is explicitly declared.
 * - Confirms that content is processed in transient server memory and immediately destroyed.
 * - NO pre-selected consent.
 * - Cancel button is prominent and immediate.
 */
import React from 'react';
import {
  Modal,
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { EphemeralAiConsent } from './types';

interface ConsentGateProps {
  visible: boolean;
  purpose: 'semantic_extraction' | 'embedding_generation' | 'question_answering';
  previewContent: string;
  onConsent: (consent: EphemeralAiConsent) => void;
  onCancel: () => void;
}

export const ConsentGate: React.FC<ConsentGateProps> = ({
  visible,
  purpose,
  previewContent,
  onConsent,
  onCancel,
}) => {
  const getPurposeDetails = () => {
    switch (purpose) {
      case 'semantic_extraction':
        return {
          title: 'Extract Entities & Topics',
          description:
            'MindMesh AI will extract key people, locations, dates, and topics from this memory in temporary server memory.',
        };
      case 'embedding_generation':
        return {
          title: 'Generate Search Vector',
          description:
            'A 1024-dimensional semantic embedding vector will be calculated to enable searching this memory locally.',
        };
      case 'question_answering':
        return {
          title: 'Synthesize Grounded Answer',
          description:
            'Selected snippets will be passed to the AI to answer your query. Server memory is destroyed immediately.',
        };
    }
  };

  const details = getPurposeDetails();

  const handleApprove = () => {
    onConsent({
      consent_granted: true,
      purpose,
      retention_policy: 'immediate_destruction',
    });
  };

  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      onRequestClose={onCancel}
    >
      <View style={styles.overlay}>
        <View style={styles.container}>
          <View style={styles.header}>
            <View style={styles.iconCircle}>
              <Ionicons name="shield-checkmark" size={24} color="#6366f1" />
            </View>
            <Text style={styles.title}>{details.title}</Text>
          </View>

          <ScrollView style={styles.body}>
            <Text style={styles.description}>{details.description}</Text>

            <View style={styles.section}>
              <Text style={styles.sectionHeader}>CONTENT TO PROCESS:</Text>
              <View style={styles.previewBox}>
                <Text style={styles.previewText} numberOfLines={4}>
                  "{previewContent}"
                </Text>
              </View>
            </View>

            <View style={styles.guaranteeBox}>
              <Ionicons name="lock-closed" size={16} color="#10b981" />
              <View style={styles.guaranteeTextContainer}>
                <Text style={styles.guaranteeTitle}>Zero-Persistence Guarantee</Text>
                <Text style={styles.guaranteeSubtitle}>
                  This text will NOT be stored in any database, logs, or backups. It is destroyed immediately after processing.
                </Text>
              </View>
            </View>
          </ScrollView>

          <View style={styles.actions}>
            <TouchableOpacity style={styles.cancelBtn} onPress={onCancel}>
              <Text style={styles.cancelText}>Cancel</Text>
            </TouchableOpacity>

            <TouchableOpacity style={styles.consentBtn} onPress={handleApprove}>
              <Text style={styles.consentText}>Approve Once</Text>
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </Modal>
  );
};

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.65)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  container: {
    backgroundColor: '#18181b',
    borderRadius: 20,
    width: '100%',
    maxHeight: '80%',
    borderWidth: 1,
    borderColor: '#27272a',
    padding: 20,
  },
  header: {
    alignItems: 'center',
    marginBottom: 16,
  },
  iconCircle: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: 'rgba(99, 102, 241, 0.15)',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 10,
  },
  title: {
    fontSize: 18,
    fontWeight: '700',
    color: '#f4f4f5',
    textAlign: 'center',
  },
  body: {
    marginBottom: 20,
  },
  description: {
    fontSize: 14,
    color: '#a1a1aa',
    lineHeight: 20,
    marginBottom: 16,
    textAlign: 'center',
  },
  section: {
    marginBottom: 16,
  },
  sectionHeader: {
    fontSize: 11,
    fontWeight: '700',
    color: '#71717a',
    letterSpacing: 0.8,
    marginBottom: 6,
  },
  previewBox: {
    backgroundColor: '#27272a',
    borderRadius: 10,
    padding: 12,
    borderLeftWidth: 3,
    borderLeftColor: '#6366f1',
  },
  previewText: {
    fontSize: 13,
    color: '#e4e4e7',
    fontStyle: 'italic',
  },
  guaranteeBox: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: 'rgba(16, 185, 129, 0.1)',
    borderRadius: 12,
    padding: 12,
    borderWidth: 1,
    borderColor: 'rgba(16, 185, 129, 0.25)',
  },
  guaranteeTextContainer: {
    marginLeft: 10,
    flex: 1,
  },
  guaranteeTitle: {
    fontSize: 13,
    fontWeight: '600',
    color: '#10b981',
    marginBottom: 2,
  },
  guaranteeSubtitle: {
    fontSize: 12,
    color: '#a1a1aa',
    lineHeight: 16,
  },
  actions: {
    flexDirection: 'row',
    gap: 12,
  },
  cancelBtn: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 12,
    backgroundColor: '#27272a',
    alignItems: 'center',
  },
  cancelText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#d4d4d8',
  },
  consentBtn: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 12,
    backgroundColor: '#6366f1',
    alignItems: 'center',
  },
  consentText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#ffffff',
  },
});
