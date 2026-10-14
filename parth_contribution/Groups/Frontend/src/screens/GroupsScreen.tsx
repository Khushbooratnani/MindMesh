import React from 'react';
import { View, Text, StyleSheet, FlatList } from 'react-native';

export const GroupsScreen = () => {
    return (
        <View style={styles.container}>
            <Text style={styles.title}>My Groups</Text>
            <FlatList
                data={[]}
                keyExtractor={(item) => item.id}
                renderItem={({ item }) => <Text>{item.name}</Text>}
                ListEmptyComponent={<Text>No groups yet.</Text>}
            />
        </View>
    );
};

const styles = StyleSheet.create({
    container: { flex: 1, padding: 16 },
    title: { fontSize: 24, fontWeight: 'bold' }
});
