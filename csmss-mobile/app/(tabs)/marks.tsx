// app/(tabs)/marks.tsx — Marks tab (student: view | teacher: select subject)
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

const GRADE_COLORS: Record<string, string> = {
  O: '#10b981', 'A+': '#3b82f6', A: '#6366f1',
  'B+': '#8b5cf6', B: '#f59e0b', C: '#f97316', F: '#ef4444',
};

export default function MarksTab() {
  const role = useAuthStore(s => s.user?.role ?? '');
  const isStaff = ['TEACHER', 'CLASS_TEACHER', 'HOD', 'SUPER_ADMIN'].includes(role);
  return isStaff ? <TeacherMarks /> : <StudentMarks />;
}

function StudentMarks() {
  const { data, isLoading, refetch, isRefetching } = useQuery({
    queryKey: ['marks-my'],
    queryFn:  () => api.get('/marks/my').then(r => r.data),
  });

  return (
    <SafeAreaView style={s.safe}>
      <View style={s.pageHeader}>
        <Text style={s.pageTitle}>My Marks</Text>
      </View>
      <ScrollView
        refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} tintColor="#3b82f6" />}
        showsVerticalScrollIndicator={false}
      >
        {isLoading ? (
          <View style={s.loader}><ActivityIndicator size="large" color="#3b82f6" /></View>
        ) : (
          <View style={s.section}>
            {data?.marks?.length === 0 && (
              <View style={s.empty}>
                <Ionicons name="bar-chart-outline" size={48} color="#5a7499" />
                <Text style={s.emptyText}>No marks uploaded yet</Text>
              </View>
            )}
            {data?.marks?.map((sub: any, i: number) => (
              <View key={i} style={s.subCard}>
                <Text style={s.subName}>{sub.subject}</Text>
                <Text style={s.subCode}>{sub.code}</Text>
                <View style={s.examList}>
                  {sub.exams.map((exam: any, j: number) => {
                    const color = GRADE_COLORS[exam.grade] ?? '#5a7499';
                    return (
                      <View key={j} style={s.examRow}>
                        <Text style={s.examLabel}>{exam.exam_label}</Text>
                        <View style={s.examRight}>
                          <Text style={s.examMarks}>{exam.marks}/{exam.max_marks}</Text>
                          <View style={[s.gradeBadge, { backgroundColor: color + '22', borderColor: color + '44' }]}>
                            <Text style={[s.gradeText, { color }]}>{exam.grade}</Text>
                          </View>
                          <Text style={[s.examPct, { color }]}>{exam.percentage}%</Text>
                        </View>
                      </View>
                    );
                  })}
                </View>
              </View>
            ))}
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

function TeacherMarks() {
  const { data, isLoading, refetch, isRefetching } = useQuery({
    queryKey: ['attendance-subjects'],
    queryFn:  () => api.get('/attendance/subjects').then(r => r.data),
  });

  return (
    <SafeAreaView style={s.safe}>
      <View style={s.pageHeader}>
        <Text style={s.pageTitle}>Upload Marks</Text>
      </View>
      <ScrollView
        refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} tintColor="#3b82f6" />}
        showsVerticalScrollIndicator={false}
      >
        {isLoading ? (
          <View style={s.loader}><ActivityIndicator size="large" color="#3b82f6" /></View>
        ) : (
          <View style={s.section}>
            <Text style={s.sectionTitle}>Select Subject</Text>
            {data?.subjects?.map((sub: any) => (
              <TouchableOpacity
                key={sub.id}
                style={s.subjectCard}
                onPress={() => router.push({ pathname: '/(more)/upload-marks', params: { subject_id: sub.id, subject_name: sub.name } })}
                activeOpacity={0.8}
              >
                <View style={s.codeBadge}><Text style={s.codeText}>{sub.code}</Text></View>
                <View style={{ flex: 1 }}>
                  <Text style={s.subjectName}>{sub.name}</Text>
                  <Text style={s.subjectClass}>{sub.class_name}</Text>
                </View>
                <Ionicons name="chevron-forward" size={18} color="#5a7499" />
              </TouchableOpacity>
            ))}
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safe:        { flex: 1, backgroundColor: '#050d1a' },
  pageHeader:  { paddingHorizontal: 20, paddingTop: 16, paddingBottom: 8 },
  pageTitle:   { color: '#f0f4ff', fontSize: 22, fontWeight: '700' },
  section:     { paddingHorizontal: 16, paddingBottom: 20 },
  sectionTitle:{ color: '#8ba4c7', fontSize: 11, fontWeight: '700', letterSpacing: 0.8, textTransform: 'uppercase', marginBottom: 12 },
  loader:      { paddingTop: 80, alignItems: 'center' },
  empty:       { alignItems: 'center', paddingTop: 60, gap: 12 },
  emptyText:   { color: '#5a7499', fontSize: 14 },

  subCard:     { backgroundColor: '#0d1f3c', borderRadius: 16, padding: 16, marginBottom: 12 },
  subName:     { color: '#f0f4ff', fontSize: 16, fontWeight: '700' },
  subCode:     { color: '#5a7499', fontSize: 12, marginBottom: 12 },
  examList:    { gap: 8 },
  examRow:     { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', backgroundColor: '#0b1830', borderRadius: 10, padding: 10 },
  examLabel:   { color: '#8ba4c7', fontSize: 13, flex: 1 },
  examRight:   { flexDirection: 'row', alignItems: 'center', gap: 8 },
  examMarks:   { color: '#e2e8f0', fontSize: 13, fontWeight: '600' },
  gradeBadge:  { borderRadius: 6, paddingHorizontal: 8, paddingVertical: 3, borderWidth: 1 },
  gradeText:   { fontWeight: '800', fontSize: 12 },
  examPct:     { fontSize: 12, fontWeight: '700', minWidth: 38, textAlign: 'right' },

  subjectCard: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#0d1f3c', borderRadius: 14, padding: 14, marginBottom: 10, gap: 12 },
  codeBadge:   { backgroundColor: '#1a56db22', borderRadius: 8, paddingHorizontal: 10, paddingVertical: 6 },
  codeText:    { color: '#3b82f6', fontWeight: '800', fontSize: 13 },
  subjectName: { color: '#e2e8f0', fontSize: 15, fontWeight: '600' },
  subjectClass:{ color: '#5a7499', fontSize: 12, marginTop: 2 },
});
