// app/(more)/timetable.tsx — Full weekly timetable screen
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  View, Text, ScrollView, TouchableOpacity,
  StyleSheet, ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import api from '../../services/api';

const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
const TODAY = DAYS[new Date().getDay() === 0 ? 0 : new Date().getDay() - 1] ?? 'Monday';

export default function TimetableScreen() {
  const [selectedDay, setSelectedDay] = useState(TODAY);

  const { data, isLoading } = useQuery({
    queryKey: ['timetable', selectedDay],
    queryFn:  () => api.get(`/timetable/?day=${selectedDay}`).then(r => r.data),
  });

  const COLORS: Record<string, string> = {
    theory:    '#3b82f6',
    practical: '#8b5cf6',
    tutorial:  '#10b981',
  };

  return (
    <SafeAreaView style={s.safe}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn}>
          <Ionicons name="arrow-back" size={20} color="#3b82f6" />
        </TouchableOpacity>
        <Text style={s.pageTitle}>Timetable</Text>
      </View>

      {/* Day selector */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.dayScroll} contentContainerStyle={s.dayRow}>
        {DAYS.map(day => (
          <TouchableOpacity
            key={day}
            style={[s.dayBtn, selectedDay === day && s.dayBtnActive]}
            onPress={() => setSelectedDay(day)}
          >
            <Text style={[s.dayText, selectedDay === day && s.dayTextActive]}>
              {day.slice(0, 3)}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      <ScrollView showsVerticalScrollIndicator={false} style={s.scroll}>
        {isLoading ? (
          <View style={s.loader}><ActivityIndicator size="large" color="#3b82f6" /></View>
        ) : data?.entries?.length === 0 ? (
          <View style={s.empty}>
            <Ionicons name="calendar-outline" size={48} color="#5a7499" />
            <Text style={s.emptyText}>No classes on {selectedDay}</Text>
          </View>
        ) : (
          <View style={s.section}>
            {data?.entries?.map((e: any, i: number) => {
              const color = COLORS[e.entry_type] ?? '#3b82f6';
              return (
                <View key={i} style={[s.periodCard, { borderLeftColor: color }]}>
                  <View style={[s.periodNumBadge, { backgroundColor: color + '22' }]}>
                    <Text style={[s.periodNum, { color }]}>P{e.period}</Text>
                  </View>
                  <View style={s.periodInfo}>
                    <Text style={s.subjectName}>{e.subject}</Text>
                    {e.teacher && <Text style={s.teacherName}>{e.teacher}</Text>}
                    {e.class_name && <Text style={s.className}>{e.class_name}</Text>}
                  </View>
                  <View style={s.periodRight}>
                    <View style={[s.typeBadge, { backgroundColor: color + '18' }]}>
                      <Text style={[s.typeText, { color }]}>
                        {e.entry_type?.charAt(0).toUpperCase() + e.entry_type?.slice(1) ?? 'Theory'}
                      </Text>
                    </View>
                    {e.batch && (
                      <Text style={s.batchText}>{e.batch}</Text>
                    )}
                  </View>
                </View>
              );
            })}
          </View>
        )}
        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safe:          { flex: 1, backgroundColor: '#050d1a' },
  header:        { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingTop: 12, paddingBottom: 4, gap: 10 },
  backBtn:       { padding: 6 },
  pageTitle:     { color: '#f0f4ff', fontSize: 20, fontWeight: '700' },
  dayScroll:     { maxHeight: 56 },
  dayRow:        { paddingHorizontal: 16, gap: 8, alignItems: 'center', paddingVertical: 8 },
  dayBtn:        { paddingHorizontal: 16, paddingVertical: 8, borderRadius: 20, backgroundColor: '#0d1f3c', borderWidth: 1, borderColor: 'rgba(59,130,246,0.15)' },
  dayBtnActive:  { backgroundColor: '#1a56db', borderColor: '#1a56db' },
  dayText:       { color: '#5a7499', fontWeight: '600', fontSize: 14 },
  dayTextActive: { color: '#fff' },
  scroll:        { flex: 1 },
  section:       { paddingHorizontal: 16, paddingTop: 8 },
  loader:        { paddingTop: 80, alignItems: 'center' },
  empty:         { alignItems: 'center', paddingTop: 80, gap: 12 },
  emptyText:     { color: '#5a7499', fontSize: 14 },
  periodCard:    { flexDirection: 'row', alignItems: 'center', backgroundColor: '#0d1f3c', borderRadius: 14, padding: 14, marginBottom: 10, borderLeftWidth: 4, gap: 12 },
  periodNumBadge:{ width: 40, height: 40, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  periodNum:     { fontWeight: '800', fontSize: 14 },
  periodInfo:    { flex: 1 },
  subjectName:   { color: '#f0f4ff', fontSize: 15, fontWeight: '700' },
  teacherName:   { color: '#8ba4c7', fontSize: 12, marginTop: 2 },
  className:     { color: '#5a7499', fontSize: 11, marginTop: 1 },
  periodRight:   { alignItems: 'flex-end', gap: 4 },
  typeBadge:     { borderRadius: 6, paddingHorizontal: 8, paddingVertical: 3 },
  typeText:      { fontSize: 11, fontWeight: '700' },
  batchText:     { color: '#8b5cf6', fontSize: 11, fontWeight: '600' },
});
