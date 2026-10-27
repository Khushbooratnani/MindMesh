import React, { useState, useEffect, useCallback } from 'react';
import { StyleSheet, View, Text, ActivityIndicator } from 'react-native';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { AuthProvider, useAuth } from './src/auth/AuthContext';
import { MindMeshLogo } from './src/components/MindMeshLogo';
import { WelcomeScreen } from './src/screens/WelcomeScreen';
import { LoginScreen } from './src/screens/LoginScreen';
import { SignUpScreen } from './src/screens/SignUpScreen';
import { ForgotPasswordScreen } from './src/screens/ForgotPasswordScreen';
import { HomeScreen } from './src/screens/HomeScreen';
import { ComposerScreen } from './src/screens/ComposerScreen';
import { MemoryDetailScreen } from './src/screens/MemoryDetailScreen';
import { VaultScreen } from './src/screens/VaultScreen';
import { LockerScreen } from './src/screens/LockerScreen';
import { MemoryItem, ScreenId } from './src/types';
import { getRawFeed } from './src/services/apiClient';
import { convertRawFeedItemToMemoryItem } from './src/services/memoryAdapter';

function MainApp() {
  const { isAuthenticated, isLoading } = useAuth();
  const [activeScreen, setActiveScreen] = useState<ScreenId>('login');
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [isLoadingFeed, setIsLoadingFeed] = useState<boolean>(false);
  const [selectedMemory, setSelectedMemory] = useState<MemoryItem | null>(null);

  // Synchronize initial screen with authentication status
  useEffect(() => {
    if (!isLoading) {
      if (isAuthenticated) {
        setActiveScreen((prev) =>
          prev === 'login' || prev === 'signup' || prev === 'forgot_password' || prev === 'welcome'
            ? 'home'
            : prev
        );
      } else {
        setActiveScreen((prev) =>
          prev === 'home' || prev === 'composer' || prev === 'memory_detail' || prev === 'vault'
            ? 'login'
            : prev
        );
      }
    }
  }, [isAuthenticated, isLoading]);

  const fetchFeed = useCallback(async () => {
    if (!isAuthenticated) return;
    setIsLoadingFeed(true);
    try {
      const feedData = await getRawFeed(150, 0);
      if (feedData && Array.isArray(feedData.items)) {
        const converted = feedData.items.map((item) =>
          convertRawFeedItemToMemoryItem(item)
        );
        setMemories(converted);
        setTotalCount(feedData.total_count ?? converted.length);
      }
    } catch (err) {
      console.warn('Could not fetch PostgreSQL raw_inputs feed:', err);
    } finally {
      setIsLoadingFeed(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    if (isAuthenticated) {
      fetchFeed();
    }
  }, [isAuthenticated, fetchFeed]);

  const handleSaveMemory = (newMemory: MemoryItem) => {
    // Prepend newly ingested memory to stream and update count
    setMemories((prev) => [newMemory, ...prev]);
    setTotalCount((prev) => prev + 1);
    setSelectedMemory(newMemory);
  };

  // 1. Startup Splash / Session Restoration Loading State
  if (isLoading) {
    return (
      <SafeAreaView style={styles.splashContainer}>
        <StatusBar style="dark" />
        <View style={styles.splashContent}>
          <MindMeshLogo size="xl" withText={true} />
          <View style={styles.splashLoader}>
            <ActivityIndicator size="small" color="#4A6B53" />
            <Text style={styles.splashText}>Restoring sovereign vault session...</Text>
          </View>
        </View>
      </SafeAreaView>
    );
  }

  // 2. Unauthenticated Navigation Flow
  if (!isAuthenticated) {
    return (
      <View style={styles.container}>
        <StatusBar style="dark" />

        {activeScreen === 'welcome' && (
          <WelcomeScreen onNavigate={(screen) => setActiveScreen(screen)} />
        )}

        {(activeScreen === 'login' ||
          activeScreen === 'home' ||
          activeScreen === 'composer' ||
          activeScreen === 'memory_detail' ||
          activeScreen === 'vault') && (
          <LoginScreen onNavigate={(screen) => setActiveScreen(screen)} />
        )}

        {activeScreen === 'signup' && (
          <SignUpScreen onNavigate={(screen) => setActiveScreen(screen)} />
        )}

        {activeScreen === 'forgot_password' && (
          <ForgotPasswordScreen onNavigate={(screen) => setActiveScreen(screen)} />
        )}
      </View>
    );
  }

  // 3. Authenticated Navigation Flow
  return (
    <View style={styles.container}>
      <StatusBar style="dark" />

      {(activeScreen === 'home' ||
        activeScreen === 'welcome' ||
        activeScreen === 'login' ||
        activeScreen === 'signup' ||
        activeScreen === 'forgot_password') && (
        <HomeScreen
          memories={memories}
          totalCount={totalCount}
          isLoadingFeed={isLoadingFeed}
          onRefreshFeed={fetchFeed}
          onNavigate={(screen) => setActiveScreen(screen)}
          onSelectMemory={(mem) => setSelectedMemory(mem)}
        />
      )}

      {activeScreen === 'vault' && (
        <VaultScreen
          onNavigate={(screen) => setActiveScreen(screen)}
          onSelectMemory={(mem) => setSelectedMemory(mem)}
        />
      )}

      {activeScreen === 'composer' && (
        <ComposerScreen
          onNavigate={(screen) => setActiveScreen(screen)}
          onSaveMemory={handleSaveMemory}
        />
      )}

      {activeScreen === 'memory_detail' && (
        <MemoryDetailScreen
          memory={selectedMemory || memories[0]}
          onNavigate={(screen) => setActiveScreen(screen)}
        />
      )}

      {activeScreen === 'locker' && (
        <LockerScreen
          onNavigate={(screen) => setActiveScreen(screen)}
        />
      )}
    </View>
  );
}

export default function App() {
  return (
    <SafeAreaProvider>
      <AuthProvider>
        <MainApp />
      </AuthProvider>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#FAF7F0',
  },
  splashContainer: {
    flex: 1,
    backgroundColor: '#FAF7F0',
    alignItems: 'center',
    justifyContent: 'center',
  },
  splashContent: {
    alignItems: 'center',
    gap: 32,
  },
  splashLoader: {
    alignItems: 'center',
    gap: 12,
  },
  splashText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#5E7A64',
    letterSpacing: 0.2,
  },
});
