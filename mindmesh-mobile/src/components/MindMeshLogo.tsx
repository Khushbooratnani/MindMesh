import React from 'react';
import { View, Text, Image, StyleSheet } from 'react-native';

interface LogoProps {
  size?: 'sm' | 'md' | 'lg' | 'xl';
  withText?: boolean;
}

export const MindMeshLogo: React.FC<LogoProps> = ({ size = 'md', withText = true }) => {
  const dimMap = {
    sm: 28,
    md: 40,
    lg: 56,
    xl: 72,
  };

  const dim = dimMap[size] || 40;

  return (
    <View style={styles.container}>
      <Image
        source={require('../../assets/mindmesh_logo.jpg')}
        style={[styles.image, { width: dim, height: dim, borderRadius: dim * 0.28 }]}
        resizeMode="cover"
      />
      {withText && (
        <View style={styles.textContainer}>
          <Text style={[styles.title, size === 'xl' ? styles.titleLg : styles.titleMd]}>
            MindMesh
          </Text>
          <Text style={styles.subtitle}>AI SECOND BRAIN</Text>
        </View>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  image: {
    borderWidth: 1,
    borderColor: '#4A6B53',
  },
  textContainer: {
    justifyContent: 'center',
  },
  title: {
    fontFamily: 'System',
    fontWeight: '800',
    color: '#233529',
    letterSpacing: -0.5,
  },
  titleMd: {
    fontSize: 18,
  },
  titleLg: {
    fontSize: 24,
  },
  subtitle: {
    fontSize: 9,
    fontWeight: '700',
    color: '#5E7A64',
    letterSpacing: 1.5,
  },
});
