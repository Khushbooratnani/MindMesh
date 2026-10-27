import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { ScreenId } from '../types';

interface DockProps {
  activeScreenId: ScreenId;
  onNavigate: (id: ScreenId) => void;
}

export const FloatingBottomDock: React.FC<DockProps> = ({
  activeScreenId,
  onNavigate,
}) => {
  return (
    <View style={styles.wrapper}>
      <View style={styles.dockContainer}>
        {/* Stream / Home Tab */}
        <TouchableOpacity
          onPress={() => onNavigate('home')}
          style={[styles.tab, activeScreenId === 'home' && styles.activeTab]}
          activeOpacity={0.8}
        >
          <Ionicons
            name={activeScreenId === 'home' ? 'layers' : 'layers-outline'}
            size={18}
            color={activeScreenId === 'home' ? '#FFFFFF' : '#5E7A64'}
          />
          <Text
            style={[
              styles.tabText,
              activeScreenId === 'home' ? styles.activeTabText : styles.inactiveTabText,
            ]}
          >
            Stream
          </Text>
        </TouchableOpacity>

        {/* Groups Tab */}
        <TouchableOpacity
          onPress={() => onNavigate('groups')}
          style={[
            styles.tab,
            activeScreenId === 'groups' || activeScreenId === 'group_detail'
              ? styles.activeTab
              : styles.secondaryTab,
          ]}
          activeOpacity={0.8}
        >
          <Ionicons
            name={
              activeScreenId === 'groups' || activeScreenId === 'group_detail'
                ? 'people'
                : 'people-outline'
            }
            size={18}
            color={
              activeScreenId === 'groups' || activeScreenId === 'group_detail'
                ? '#FFFFFF'
                : '#4A6B53'
            }
          />
          <Text
            style={[
              styles.tabText,
              activeScreenId === 'groups' || activeScreenId === 'group_detail'
                ? styles.activeTabText
                : styles.inactiveTabText,
            ]}
          >
            Groups
          </Text>
        </TouchableOpacity>

        {/* Center + Capture Memory Tab */}
        <TouchableOpacity
          onPress={() => onNavigate('composer')}
          style={styles.centerAddButton}
          activeOpacity={0.85}
        >
          <View style={styles.addCircle}>
            <Ionicons name="add" size={24} color="#FFFFFF" />
          </View>
        </TouchableOpacity>

        {/* Brain Search Tab / Vault */}
        <TouchableOpacity
          onPress={() => onNavigate('vault')}
          style={[styles.tab, activeScreenId === 'vault' ? styles.activeTab : styles.secondaryTab]}
          activeOpacity={0.8}
        >
          <Ionicons
            name={activeScreenId === 'vault' ? 'sparkles' : 'sparkles-outline'}
            size={18}
            color={activeScreenId === 'vault' ? '#FFFFFF' : '#4A6B53'}
          />
          <Text
            style={[
              styles.tabText,
              activeScreenId === 'vault' ? styles.activeTabText : styles.inactiveTabText,
            ]}
          >
            Vault
          </Text>
        </TouchableOpacity>

        {/* Private Locker Tab */}
        <TouchableOpacity
          onPress={() => onNavigate('locker')}
          style={[styles.tab, activeScreenId === 'locker' ? styles.activeTab : styles.secondaryTab]}
          activeOpacity={0.8}
        >
          <Ionicons
            name={activeScreenId === 'locker' ? 'shield' : 'shield-outline'}
            size={18}
            color={activeScreenId === 'locker' ? '#FFFFFF' : '#4A6B53'}
          />
          <Text
            style={[
              styles.tabText,
              activeScreenId === 'locker' ? styles.activeTabText : styles.inactiveTabText,
            ]}
          >
            Locker
          </Text>
        </TouchableOpacity>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  wrapper: {
    position: 'absolute',
    bottom: 24,
    left: 20,
    right: 20,
    alignItems: 'center',
  },
  dockContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderRadius: 30,
    paddingVertical: 6,
    paddingHorizontal: 8,
    borderWidth: 1,
    borderColor: '#D5CDBC',
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.12,
    shadowRadius: 16,
    elevation: 8,
    gap: 4,
  },
  tab: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 7,
    paddingHorizontal: 9,
    borderRadius: 22,
    gap: 4,
  },
  secondaryTab: {
    backgroundColor: '#FAF7F0',
  },
  activeTab: {
    backgroundColor: '#4A6B53',
  },
  tabText: {
    fontSize: 11,
    fontWeight: '700',
  },
  activeTabText: {
    color: '#FFFFFF',
  },
  inactiveTabText: {
    color: '#5E7A64',
  },
  centerAddButton: {
    padding: 2,
  },
  addCircle: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#4A6B53',
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#4A6B53',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.35,
    shadowRadius: 8,
    elevation: 4,
  },
});
