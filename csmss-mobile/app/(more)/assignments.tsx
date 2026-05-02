// app/(more)/assignments.tsx — Assignments list (student: view/submit status | teacher: list)
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

export default function AssignmentsScreen() {
  const role = useAuthStore(s => s.user?.role ?? '');
  const { data, isLoading, refetch, isRefetching } = useQuery({
    queryKey: ['assignments'],
    queryFn:  () => api.get('/assignments/?per_page=30').then(r => r.data),
  });

  const today = new Date().toISOString().split('T')[0];

  return (
    <SafeAreaView style={s.safe}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn}>
          <Ionicons name="arrow-back" size={20} color="#3b82f6" />
        </TouchableOpacity>
        <Text style={s.pageTitle}>Assignments</Text>
      </View>

      <ScrollView
        refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} tintColor="#3b82f6" />}
        showsVerticalScrollIndicator={false}
      >
        {isLoading ? (
          <View style={s.loader}><ActivityIndicator size="large" color="#3b82f6" /></View>
        ) : data?.assignments?.length === 0 ? (
          <View style={s.empty}>
            <Ionicons name="document-text-outline" size={48} color="#5a7499" />
            <Text style={s.emptyText}>No assignments</Text>
          </View>
        ) : (
          <View style={s.section}>
            {data?.assignments?.map((a: any) => {
              const isOverdue  = a.due_date && a.due_date < today;
              const isDueSoon  = a.due_date && !isOverdue && a.due_date <= new Date(Date.now() + 2*86400000).toISOString().split('T')[0];
              const statusColor = a.submitted ? '#10b981' : isOverdue ? '#ef4444' : isDueSoon ? '#f59e0b' : '#5a7499';

              return (
                <View key={a.id} style={[s.assignCard, { borderLeftColor: statusColor }]}>
                  <View style={s.assignHeader}>
                    <View style={{ flex: 1 }}>
                      <Text style={s.assignTitle}>{a.title}</Text>
                      <Text style={s.assignSubject}>{a.subject}</Text>
                    </View>
                    {a.submitted ? (
                      <View style={s.submittedBadge}>
                        <Ionicons name="checkmark-circle" size={14} color="#10b981" />
                        <Text style={s.submittedText}>Submitted</Text>
                      </View>
                    ) : isOverdue ? (
                      <View style={s.overdueBadge}>
                        <Ionicons name="close-circle" size={14} color="#ef4444" />
                        <Text style={s.overdueText}>Overdue</Text>
                      </View>
                    ) : (
                      <View style={[s.dueBadge, { backgroundColor: isDueSoon ? '#f59e0b22' : '#5a749922' }]}>
                        <Ionicons name="time-outline" size={14} color={isDueSoon ? '#f59e0b' : '#5a7499'} />
                        <Text style={[s.dueText, { color: isDueSoon ? '#f59e0b' : '#5a7499' }]}>
                          {a.due_date}
                        </Text>
                      </View>
                    )}
                  </View>
                  {a.description ? (
                    <Text style={s.assignDesc} numberOfLines={2}>{a.description}</Text>
                  ) : null}
                  <Text style={s.dueLabel}>Due: {a.due_date ?? 'No deadline'}</Text>
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
  safe:            { flex: 1, backgroundColor: '#050d1a' },
  header:          { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingTop: 12, paddingBottom: 8, gap: 10 },
  backBtn:         { padding: 6 },
  pageTitle:       { color: '#f0f4ff', fontSize: 20, fontWeight: '700' },
  section:         { paddingHorizontal: 16, paddingTop: 8 },
  loader:          { paddingTop: 80, alignItems: 'center' },
  empty:           { alignItems: 'center', paddingTop: 80, gap: 12 },
  emptyText:       { color: '#5a7499', fontSize: 14 },

  assignCard:      { backgroundColor: '#0d1f3c', borderRadius: 14, padding: 14, marginBottom: 10, borderLeftWidth: 3 },
  assignHeader:    { flexDirection: 'row', alignItems: 'flex-start', gap: 10, marginBottom: 6 },
  assignTitle:     { color: '#f0f4ff', fontSize: 15, fontWeight: '700' },
  assignSubject:   { color: '#5a7499', fontSize: 12, marginTop: 2 },
  assignDesc:      { color: '#8ba4c7', fontSize: 13, lineHeight: 18, marginBottom: 6 },
  dueLabel:        { color: '#5a7499', fontSize: 11 },

  submittedBadge:  { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#10b98122', borderRadius: 8, paddingHorizontal: 8, paddingVertical: 4 },
  submittedText:   { color: '#10b981', fontSize: 11, fontWeight: '700' },
  overdueBadge:    { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#ef444422', borderRadius: 8, paddingHorizontal: 8, paddingVertical: 4 },
  overdueText:     { color: '#ef4444', fontSize: 11, fontWeight: '700' },
  dueBadge:        { flexDirection: 'row', alignItems: 'center', gap: 4, borderRadius: 8, paddingHorizontal: 8, paddingVertical: 4 },
  dueText:         { fontSize: 11, fontWeight: '600' },
});
