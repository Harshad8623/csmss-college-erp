// app/(tabs)/attendance.tsx — Attendance Tab (student view + teacher mark)
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
import { useAuthStore } from '../../store/auth.store';

const ROLES_STAFF = ['TEACHER', 'CLASS_TEACHER', 'HOD', 'SUPER_ADMIN'];

export default function AttendanceTab() {
  const role = useAuthStore(s => s.user?.role ?? '');
  const isStaff = ROLES_STAFF.includes(role);
  return isStaff ? <TeacherAttendance /> : <StudentAttendance />;
}

// ── Student View ──────────────────────────────────────────────────────────
function StudentAttendance() {
  const { data, isLoading, refetch, isRefetching } = useQuery({
    queryKey: ['attendance-my'],
    queryFn:  () => api.get('/attendance/my').then(r => r.data),
  });

  const getColor = (pct: number) =>
    pct >= 75 ? '#10b981' : pct >= 60 ? '#f59e0b' : '#ef4444';

  return (
    <SafeAreaView style={s.safe}>
      <View style={s.pageHeader}>
        <Text style={s.pageTitle}>My Attendance</Text>
      </View>
      <ScrollView
        refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} tintColor="#3b82f6" />}
        showsVerticalScrollIndicator={false}
      >
        {isLoading ? (
          <View style={s.loader}><ActivityIndicator size="large" color="#3b82f6" /></View>
        ) : data ? (
          <>
            {/* Overall Card */}
            <View style={[s.overallCard, { borderColor: data.is_defaulter ? '#ef444430' : '#10b98130' }]}>
              {data.is_defaulter && (
                <View style={s.defaulterBanner}>
                  <Ionicons name="warning" size={14} color="#ef4444" />
                  <Text style={s.defaulterText}>Defaulter — Below 75%! Contact your Class Teacher.</Text>
                </View>
              )}
              <Text style={[s.overallPct, { color: getColor(data.overall_percentage) }]}>
                {data.overall_percentage}%
              </Text>
              <Text style={s.overallLabel}>Overall Attendance</Text>
            </View>

            {/* Subject List */}
            <View style={s.section}>
              <Text style={s.sectionTitle}>Subject-wise Breakdown</Text>
              {data.subjects?.map((sub: any, i: number) => (
                <View key={i} style={s.subCard}>
                  <View style={s.subHeader}>
                    <View>
                      <Text style={s.subName}>{sub.subject}</Text>
                      <Text style={s.subCode}>{sub.code}</Text>
                    </View>
                    <View style={[s.pctBadge, { backgroundColor: getColor(sub.percentage) + '22', borderColor: getColor(sub.percentage) + '44' }]}>
                      <Text style={[s.pctText, { color: getColor(sub.percentage) }]}>{sub.percentage}%</Text>
                    </View>
                  </View>
                  <View style={s.barBg}>
                    <View style={[s.barFill, { width: `${Math.min(100, sub.percentage)}%`, backgroundColor: getColor(sub.percentage) }]} />
                  </View>
                  <View style={s.subStats}>
                    <Text style={s.subStat}>✅ {sub.present} Present</Text>
                    <Text style={s.subStat}>❌ {sub.absent} Absent</Text>
                    <Text style={s.subStat}>📅 {sub.total} Classes</Text>
                  </View>
                </View>
              ))}
            </View>
          </>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
}

// ── Teacher View ──────────────────────────────────────────────────────────
function TeacherAttendance() {
  const { data, isLoading, refetch, isRefetching } = useQuery({
    queryKey: ['attendance-subjects'],
    queryFn:  () => api.get('/attendance/subjects').then(r => r.data),
  });

  return (
    <SafeAreaView style={s.safe}>
      <View style={s.pageHeader}>
        <Text style={s.pageTitle}>Mark Attendance</Text>
      </View>
      <ScrollView
        refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} tintColor="#3b82f6" />}
        showsVerticalScrollIndicator={false}
      >
        {isLoading ? (
          <View style={s.loader}><ActivityIndicator size="large" color="#3b82f6" /></View>
        ) : (
          <View style={s.section}>
            <Text style={s.sectionTitle}>My Subjects</Text>
            {data?.subjects?.map((sub: any) => (
              <TouchableOpacity
                key={sub.id}
                style={s.subjectCard}
                onPress={() => router.push({ pathname: '/(more)/mark-attendance', params: { subject_id: sub.id, subject_name: sub.name } })}
                activeOpacity={0.8}
              >
                <View style={s.subjectLeft}>
                  <View style={s.codeBadge}>
                    <Text style={s.codeText}>{sub.code}</Text>
                  </View>
                </View>
                <View style={s.subjectInfo}>
                  <Text style={s.subjectName}>{sub.name}</Text>
                  <Text style={s.subjectClass}>{sub.class_name}</Text>
                  {sub.last_marked && (
                    <Text style={s.lastMarked}>Last: {sub.last_marked}</Text>
                  )}
                </View>
                <View style={s.subjectRight}>
                  {sub.marked_today ? (
                    <View style={s.markedBadge}>
                      <Ionicons name="checkmark-circle" size={14} color="#10b981" />
                      <Text style={s.markedText}>Done</Text>
                    </View>
                  ) : (
                    <Ionicons name="chevron-forward" size={18} color="#5a7499" />
                  )}
                </View>
              </TouchableOpacity>
            ))}
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safe:          { flex: 1, backgroundColor: '#050d1a' },
  pageHeader:    { paddingHorizontal: 20, paddingTop: 16, paddingBottom: 8 },
  pageTitle:     { color: '#f0f4ff', fontSize: 22, fontWeight: '700' },
  loader:        { paddingTop: 80, alignItems: 'center' },
  section:       { paddingHorizontal: 16, marginTop: 8 },
  sectionTitle:  { color: '#8ba4c7', fontSize: 11, fontWeight: '700', letterSpacing: 0.8, textTransform: 'uppercase', marginBottom: 12 },

  overallCard:   { margin: 16, backgroundColor: '#0d1f3c', borderRadius: 20, padding: 24, borderWidth: 1, alignItems: 'center', gap: 6 },
  defaulterBanner: { flexDirection: 'row', gap: 6, alignItems: 'center', backgroundColor: 'rgba(239,68,68,0.08)', paddingHorizontal: 12, paddingVertical: 8, borderRadius: 10, borderWidth: 1, borderColor: 'rgba(239,68,68,0.2)', marginBottom: 4 },
  defaulterText: { color: '#ef4444', fontSize: 12, fontWeight: '600', flex: 1 },
  overallPct:    { fontSize: 52, fontWeight: '800' },
  overallLabel:  { color: '#5a7499', fontSize: 14 },

  subCard:       { backgroundColor: '#0d1f3c', borderRadius: 14, padding: 16, marginBottom: 10 },
  subHeader:     { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 },
  subName:       { color: '#e2e8f0', fontSize: 15, fontWeight: '600' },
  subCode:       { color: '#5a7499', fontSize: 12, marginTop: 2 },
  pctBadge:      { borderRadius: 8, paddingHorizontal: 10, paddingVertical: 4, borderWidth: 1 },
  pctText:       { fontWeight: '800', fontSize: 14 },
  barBg:         { height: 6, backgroundColor: '#0b1830', borderRadius: 3, overflow: 'hidden', marginBottom: 8 },
  barFill:       { height: 6, borderRadius: 3 },
  subStats:      { flexDirection: 'row', gap: 12 },
  subStat:       { color: '#5a7499', fontSize: 11 },

  subjectCard:   { flexDirection: 'row', alignItems: 'center', backgroundColor: '#0d1f3c', borderRadius: 14, padding: 14, marginBottom: 10, gap: 12 },
  subjectLeft:   {},
  codeBadge:     { backgroundColor: '#1a56db22', borderRadius: 8, paddingHorizontal: 10, paddingVertical: 6 },
  codeText:      { color: '#3b82f6', fontWeight: '800', fontSize: 13 },
  subjectInfo:   { flex: 1 },
  subjectName:   { color: '#e2e8f0', fontSize: 15, fontWeight: '600' },
  subjectClass:  { color: '#5a7499', fontSize: 12, marginTop: 2 },
  lastMarked:    { color: '#3a4d66', fontSize: 11, marginTop: 2 },
  subjectRight:  {},
  markedBadge:   { flexDirection: 'row', gap: 4, alignItems: 'center', backgroundColor: '#10b98120', borderRadius: 8, paddingHorizontal: 8, paddingVertical: 4 },
  markedText:    { color: '#10b981', fontSize: 12, fontWeight: '600' },
});
