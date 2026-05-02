// app/(more)/sessions.tsx — Practical sessions list (placeholder → uses web for full detail)
import { useQuery } from '@tanstack/react-query';
import { View, Text, StyleSheet, ActivityIndicator, TouchableOpacity } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';

export default function SessionsScreen() {
  return (
    <SafeAreaView style={s.safe}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn}>
          <Ionicons name="arrow-back" size={20} color="#3b82f6" />
        </TouchableOpacity>
        <Text style={s.pageTitle}>Practical Sessions</Text>
      </View>
      <View style={s.center}>
        <Ionicons name="flask-outline" size={56} color="#8b5cf6" />
        <Text style={s.title}>Practical Records</Text>
        <Text style={s.subtitle}>
          Practical session records, attendance and grades are managed via the web portal.{'\n\n'}
          Open the CSMSS ERP website to access practical batch records.
        </Text>
        <View style={s.infoBanner}>
          <Ionicons name="information-circle-outline" size={16} color="#8b5cf6" />
          <Text style={s.infoText}>
            This module will be added to the mobile app in a future update.
          </Text>
        </View>
      </View>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safe:       { flex: 1, backgroundColor: '#050d1a' },
  header:     { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingTop: 12, paddingBottom: 8, gap: 10 },
  backBtn:    { padding: 6 },
  pageTitle:  { color: '#f0f4ff', fontSize: 20, fontWeight: '700' },
  center:     { flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 32, gap: 12 },
  title:      { color: '#f0f4ff', fontSize: 20, fontWeight: '700' },
  subtitle:   { color: '#8ba4c7', fontSize: 14, textAlign: 'center', lineHeight: 22 },
  infoBanner: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#8b5cf610', borderRadius: 10, padding: 12, borderWidth: 1, borderColor: '#8b5cf620' },
  infoText:   { color: '#8b5cf6', fontSize: 12, flex: 1 },
});
