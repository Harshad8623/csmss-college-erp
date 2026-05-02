// app/(more)/class-attendance.tsx — CT view: attendance report for all subjects in class
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  View, Text, ScrollView, RefreshControl, TouchableOpacity,
  StyleSheet, ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import api from '../../services/api';

export default function ClassAttendanceScreen() {
  const { data, isLoading, refetch, isRefetching } = useQuery({
    queryKey: ['class-attendance'],
    queryFn:  () => api.get('/attendance/ct-view').then(r => r.data),
  });

  const getColor = (pct: number) =>
    pct >= 75 ? '#10b981' : pct >= 60 ? '#f59e0b' : '#ef4444';

  return (
    <SafeAreaView style={s.safe}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn}>
          <Ionicons name="arrow-back" size={20} color="#3b82f6" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={s.pageTitle}>Class Attendance</Text>
          {data?.class_name && <Text style={s.classSub}>{data.class_name}</Text>}
        </View>
      </View>

      <ScrollView
        refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} tintColor="#3b82f6" />}
        showsVerticalScrollIndicator={false}
      >
        {isLoading ? (
          <View style={s.loader}><ActivityIndicator size="large" color="#3b82f6" /></View>
        ) : (
          <>
            {/* Summary row */}
            {data && (
              <View style={s.summaryRow}>
                <View style={s.summaryItem}>
                  <Text style={s.summaryVal}>{data.total_students}</Text>
                  <Text style={s.summaryLbl}>Students</Text>
                </View>
                <View style={s.summaryItem}>
                  <Text style={[s.summaryVal, { color: '#ef4444' }]}>{data.defaulters}</Text>
                  <Text style={s.summaryLbl}>Defaulters</Text>
                </View>
                <View style={s.summaryItem}>
                  <Text style={[s.summaryVal, { color: '#10b981' }]}>{data.above_75}</Text>
                  <Text style={s.summaryLbl}>Above 75%</Text>
                </View>
              </View>
            )}

            {/* Student list with overall % */}
            <View style={s.section}>
              <Text style={s.sectionTitle}>Student-wise Attendance</Text>
              {data?.students?.map((st: any, i: number) => {
                const color = getColor(st.overall_pct);
                return (
                  <View key={i} style={s.studentRow}>
                    <Text style={s.rollNo}>{st.roll_no}</Text>
                    <View style={{ flex: 1 }}>
                      <Text style={s.name}>{st.name}</Text>
                      {st.overall_pct < 75 && (
                        <Text style={s.defaulterTag}>⚠️ Defaulter</Text>
                      )}
                    </View>
                    <View style={[s.pctBadge, { backgroundColor: color + '22', borderColor: color + '44' }]}>
                      <Text style={[s.pctText, { color }]}>{st.overall_pct}%</Text>
                    </View>
                  </View>
                );
              })}
            </View>

            {/* Subject-wise summary */}
            {data?.subjects?.length > 0 && (
              <View style={s.section}>
                <Text style={s.sectionTitle}>Subject-wise Avg</Text>
                {data.subjects.map((sub: any, i: number) => {
                  const color = getColor(sub.avg_pct);
                  return (
                    <View key={i} style={s.subjectRow}>
                      <Text style={s.subjectName}>{sub.name}</Text>
                      <View style={s.subjectRight}>
                        <View style={s.barBg}>
                          <View style={[s.barFill, { width: `${Math.min(100, sub.avg_pct)}%`, backgroundColor: color }]} />
                        </View>
                        <Text style={[s.pctSmall, { color }]}>{sub.avg_pct}%</Text>
                      </View>
                    </View>
                  );
                })}
              </View>
            )}
          </>
        )}
        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safe:        { flex: 1, backgroundColor: '#050d1a' },
  header:      { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingTop: 12, paddingBottom: 8, gap: 10 },
  backBtn:     { padding: 6 },
  pageTitle:   { color: '#f0f4ff', fontSize: 20, fontWeight: '700' },
  classSub:    { color: '#3b82f6', fontSize: 12, fontWeight: '600' },
  loader:      { paddingTop: 80, alignItems: 'center' },

  summaryRow:  { flexDirection: 'row', justifyContent: 'space-around', backgroundColor: '#0d1f3c', margin: 16, borderRadius: 14, paddingVertical: 14 },
  summaryItem: { alignItems: 'center' },
  summaryVal:  { color: '#f0f4ff', fontSize: 22, fontWeight: '800' },
  summaryLbl:  { color: '#5a7499', fontSize: 11 },

  section:     { paddingHorizontal: 16, marginTop: 4, paddingBottom: 8 },
  sectionTitle:{ color: '#8ba4c7', fontSize: 11, fontWeight: '700', letterSpacing: 0.8, textTransform: 'uppercase', marginBottom: 10 },

  studentRow:  { flexDirection: 'row', alignItems: 'center', backgroundColor: '#0d1f3c', borderRadius: 10, padding: 12, marginBottom: 6, gap: 10 },
  rollNo:      { color: '#5a7499', fontSize: 12, width: 36 },
  name:        { color: '#e2e8f0', fontSize: 14, fontWeight: '600' },
  defaulterTag:{ color: '#ef4444', fontSize: 11, marginTop: 2 },
  pctBadge:    { borderRadius: 8, paddingHorizontal: 8, paddingVertical: 4, borderWidth: 1 },
  pctText:     { fontWeight: '800', fontSize: 13 },

  subjectRow:  { flexDirection: 'row', alignItems: 'center', backgroundColor: '#0d1f3c', borderRadius: 10, padding: 12, marginBottom: 6, gap: 12 },
  subjectName: { color: '#8ba4c7', fontSize: 13, flex: 1 },
  subjectRight:{ flexDirection: 'row', alignItems: 'center', gap: 8, width: 120 },
  barBg:       { flex: 1, height: 6, backgroundColor: '#0b1830', borderRadius: 3, overflow: 'hidden' },
  barFill:     { height: 6, borderRadius: 3 },
  pctSmall:    { fontWeight: '700', fontSize: 12, width: 36, textAlign: 'right' },
});
