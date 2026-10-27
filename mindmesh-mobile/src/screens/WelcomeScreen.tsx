import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { MindMeshLogo } from '../components/MindMeshLogo';
import { ScreenId } from '../types';

interface WelcomeProps {
  onNavigate: (id: ScreenId) => void;
}

export const WelcomeScreen: React.FC<WelcomeProps> = ({ onNavigate }) => {
  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.container}>
        {/* Top Branding Section */}
        <View style={styles.heroSection}>
          <MindMeshLogo size="xl" withText={true} />

          <View style={styles.headerTextGroup}>
            <Text style={styles.mainTitle}>Sovereign Second Brain</Text>
            <Text style={styles.subtitle}>
              Capture spontaneous voice, photos, and notes. Query and structure your life with local AI.
            </Text>
          </View>
        </View>

        {/* Feature Highlights */}
        <View style={styles.featureGroup}>
          <View style={styles.featureCard}>
            <View style={styles.iconCircle}>
              <Ionicons name="hardware-chip-outline" size={20} color="#4A6B53" />
            </View>
            <View style={styles.featureText}>
              <Text style={styles.featureTitle}>Zero-Friction Recall</Text>
              <Text style={styles.featureDesc}>
                Understands speech, images, and notes with Qwen Phase 1 structured extraction.
              </Text>
            </View>
          </View>

          <View style={styles.featureCard}>
            <View style={styles.iconCircle}>
              <Ionicons name="shield-checkmark-outline" size={20} color="#4A6B53" />
            </View>
            <View style={styles.featureText}>
              <Text style={styles.featureTitle}>PostgreSQL & Sovereign Vault</Text>
              <Text style={styles.featureDesc}>
                Structured MemoryV1 entities, topics, and temporal links saved securely.
              </Text>
            </View>
          </View>
        </View>

        {/* Action Button */}
        <View style={styles.actionSection}>
          <TouchableOpacity
            style={styles.primaryButton}
            onPress={() => onNavigate('login')}
            activeOpacity={0.88}
          >
            <Text style={styles.primaryButtonText}>Get Started / Sign In</Text>
            <Ionicons name="arrow-forward" size={18} color="#FFFFFF" />
          </TouchableOpacity>
        </View>
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
    paddingHorizontal: 24,
    paddingVertical: 20,
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  heroSection: {
    alignItems: 'center',
    paddingTop: 36,
    width: '100%',
  },
  headerTextGroup: {
    alignItems: 'center',
    marginTop: 20,
    paddingHorizontal: 12,
  },
  mainTitle: {
    fontSize: 26,
    fontWeight: '800',
    color: '#233529',
    textAlign: 'center',
    letterSpacing: -0.5,
  },
  subtitle: {
    fontSize: 13,
    color: '#5E7A64',
    textAlign: 'center',
    marginTop: 8,
    lineHeight: 19,
  },
  featureGroup: {
    width: '100%',
    gap: 12,
    marginVertical: 20,
  },
  featureCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    padding: 14,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: '#E5DFD5',
    gap: 14,
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 6,
    elevation: 1,
  },
  iconCircle: {
    width: 42,
    height: 42,
    borderRadius: 14,
    backgroundColor: '#FAF7F0',
    borderWidth: 1,
    borderColor: '#D5CDBC',
    alignItems: 'center',
    justifyContent: 'center',
  },
  featureText: {
    flex: 1,
  },
  featureTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: '#233529',
  },
  featureDesc: {
    fontSize: 11,
    color: '#5E7A64',
    marginTop: 2,
    lineHeight: 15,
  },
  actionSection: {
    width: '100%',
    paddingBottom: 16,
  },
  primaryButton: {
    backgroundColor: '#4A6B53',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 16,
    borderRadius: 20,
    gap: 10,
    shadowColor: '#4A6B53',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.25,
    shadowRadius: 10,
    elevation: 4,
  },
  primaryButtonText: {
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: '700',
    letterSpacing: 0.2,
  },
});
