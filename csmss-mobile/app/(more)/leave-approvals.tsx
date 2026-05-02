// app/(more)/leave-approvals.tsx — TG/CT can approve or reject leaves
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  View, Text, ScrollView, RefreshControl, TouchableOpacity,
  StyleSheet, ActivityIndicator, Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import api from '../../services/api';

export default function LeaveApprovalsScreen() {
  const queryClient = useQueryClient();
  const { data, isLoading, refetch, isRefetching } = useQuery({
    queryKey: ['leaves-pending'],
    queryFn:  () => api.get('/leaves/?role=staff').then(r => r.data),
  });

  const mutation = useMutation({
    mutationFn: ({ id, action, comment }: { id: number; action: string; comment?: string }) =>
      api.post(`/leaves/${id}/review`, { action, comment }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['leaves-pending'] });
    },
    onError: (err: any) => Alert.alert('Error', err?.response?.data?.error ?? 'Action failed.'),
  });

  const handleAction = (id: number, action: 'approve' | 'reject') => {
    Alert.alert(
      action === 'approve' ? '✅ Approve Leave' : '❌ Reject Leave',
      `Are you sure you want to ${action} this leave application?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: action === 'approve' ? 'Approve' : 'Reject',
          style: action === 'reject' ? 'destructive' : 'default',
          onPress: () => mutation.mutate({ id, action }),
        },
      ]
    );
  };

  const leaves = data?.leaves ?? [];
  const pending = leaves.filter((l: any) =>
    l.status === 'PENDING_TG' || l.status === 'PENDING_CT'
  );
  const reviewed = leaves.filter((l: any) =>
    l.status !== 'PENDING_TG' && l.status !== 'PENDING_CT'
  );

  const STATUS_COLORS: Record<string, string> = {
    PENDING_TG: '#f59e0b', PENDING_CT: '#f59e0b',
    APPROVED: '#10b981', REJECTED: '#ef4444',
  };

  return (
    <SafeAreaView style={s.safe}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn}>
          <Ionicons name="arrow-back" size={20} color="#3b82f6" />
        </TouchableOpacity>
        <Text style={s.pageTitle}>Leave Approvals</Text>
        {pending.length > 0 && (
          <View style={s.pendingBadge}>
            <Text style={s.pendingBadgeText}>{pending.length}</Text>
          </View>
        )}
      </View>

      <ScrollView
        refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} tintColor="#3b82f6" />}
        showsVerticalScrollIndicator={false}
      >
        {isLoading ? (
          <View style={s.loader}><ActivityIndicator size="large" color="#3b82f6" /></View>
        ) : (
          <>
            {/* Pending */}
            {pending.length > 0 && (
              <View style={s.section}>
                <Text style={s.sectionTitle}>Pending ({pending.length})</Text>
                {pending.map((l: any) => (
                  <View key={l.id} style={[s.leaveCard, s.pendingCard]}>
                    <View style={s.studentRow}>
                      <View style={s.avatarSmall}>
                        <Text style={s.avatarText}>{l.student_name?.[0] ?? 'S'}</Text>
                      </View>
                      <View style={{ flex: 1 }}>
                        <Text style={s.studentName}>{l.student_name}</Text>
                        <Text style={s.rollNo}>Roll: {l.roll_no} • {l.class_name}</Text>
                      </View>
                      <View style={[s.statusBadge, { backgroundColor: '#f59e0b22' }]}>
                        <Text style={[s.statusText, { color: '#f59e0b' }]}>Pending</Text>
                      </View>
                    </View>

                    <View style={s.leaveDetails}>
                      <Text style={s.leaveType}>
                        {l.leave_type?.replace('_', ' ').replace(/\b\w/g, (c: string) => c.toUpperCase())}
                      </Text>
                      <Text style={s.leaveDates}>📅 {l.start_date} → {l.end_date}</Text>
                      <Text style={s.leaveReason}>{l.reason}</Text>
                    </View>

                    <View style={s.actionRow}>
                      <TouchableOpacity
                        style={[s.actionBtn, s.approveBtn, mutation.isPending && s.btnDisabled]}
                        onPress={() => handleAction(l.id, 'approve')}
                        disabled={mutation.isPending}
                      >
                        <Ionicons name="checkmark" size={16} color="#fff" />
                        <Text style={s.actionBtnText}>Approve</Text>
                      </TouchableOpacity>
                      <TouchableOpacity
                        style={[s.actionBtn, s.rejectBtn, mutation.isPending && s.btnDisabled]}
                        onPress={() => handleAction(l.id, 'reject')}
                        disabled={mutation.isPending}
                      >
                        <Ionicons name="close" size={16} color="#fff" />
                        <Text style={s.actionBtnText}>Reject</Text>
                      </TouchableOpacity>
                    </View>
                  </View>
                ))}
              </View>
            )}

            {/* Reviewed */}
            {reviewed.length > 0 && (
              <View style={s.section}>
                <Text style={s.sectionTitle}>Recently Reviewed</Text>
                {reviewed.slice(0, 10).map((l: any) => {
                  const color = STATUS_COLORS[l.status] ?? '#5a7499';
                  return (
                    <View key={l.id} style={[s.leaveCard, { borderLeftColor: color }]}>
                      <View style={s.studentRow}>
                        <View style={s.avatarSmall}>
                          <Text style={s.avatarText}>{l.student_name?.[0] ?? 'S'}</Text>
                        </View>
                        <View style={{ flex: 1 }}>
                          <Text style={s.studentName}>{l.student_name}</Text>
                          <Text style={s.leaveDates}>{l.start_date} → {l.end_date}</Text>
                        </View>
                        <View style={[s.statusBadge, { backgroundColor: color + '22' }]}>
                          <Text style={[s.statusText, { color }]}>
                            {l.status === 'APPROVED' ? 'Approved' : 'Rejected'}
                          </Text>
                        </View>
                      </View>
                    </View>
                  );
                })}
              </View>
            )}

            {pending.length === 0 && reviewed.length === 0 && (
              <View style={s.empty}>
                <Ionicons name="walk-outline" size={48} color="#5a7499" />
                <Text style={s.emptyText}>No leave applications</Text>
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
  safe:          { flex: 1, backgroundColor: '#050d1a' },
  header:        { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingTop: 12, paddingBottom: 8, gap: 10 },
  backBtn:       { padding: 6 },
  pageTitle:     { color: '#f0f4ff', fontSize: 20, fontWeight: '700', flex: 1 },
  pendingBadge:  { backgroundColor: '#f59e0b', borderRadius: 10, width: 24, height: 24, alignItems: 'center', justifyContent: 'center' },
  pendingBadgeText: { color: '#050d1a', fontSize: 12, fontWeight: '800' },
  section:       { paddingHorizontal: 16, paddingTop: 8 },
  sectionTitle:  { color: '#8ba4c7', fontSize: 11, fontWeight: '700', letterSpacing: 0.8, textTransform: 'uppercase', marginBottom: 10 },
  loader:        { paddingTop: 80, alignItems: 'center' },
  empty:         { alignItems: 'center', paddingTop: 80, gap: 12 },
  emptyText:     { color: '#5a7499', fontSize: 14 },

  leaveCard:     { backgroundColor: '#0d1f3c', borderRadius: 14, padding: 14, marginBottom: 10, borderLeftWidth: 3, borderLeftColor: '#5a7499' },
  pendingCard:   { borderLeftColor: '#f59e0b', borderWidth: 1, borderColor: 'rgba(245,158,11,0.2)' },
  studentRow:    { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 10 },
  avatarSmall:   { width: 36, height: 36, borderRadius: 18, backgroundColor: '#1a56db22', alignItems: 'center', justifyContent: 'center' },
  avatarText:    { color: '#3b82f6', fontWeight: '800', fontSize: 14 },
  studentName:   { color: '#f0f4ff', fontSize: 14, fontWeight: '600' },
  rollNo:        { color: '#5a7499', fontSize: 11 },
  statusBadge:   { borderRadius: 8, paddingHorizontal: 8, paddingVertical: 4 },
  statusText:    { fontSize: 11, fontWeight: '700' },

  leaveDetails:  { marginBottom: 12, gap: 4 },
  leaveType:     { color: '#8ba4c7', fontSize: 12, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.5 },
  leaveDates:    { color: '#3b82f6', fontSize: 13, fontWeight: '600' },
  leaveReason:   { color: '#8ba4c7', fontSize: 13 },

  actionRow:     { flexDirection: 'row', gap: 10 },
  actionBtn:     { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, borderRadius: 10, paddingVertical: 10 },
  approveBtn:    { backgroundColor: '#10b981' },
  rejectBtn:     { backgroundColor: '#ef4444' },
  btnDisabled:   { opacity: 0.5 },
  actionBtnText: { color: '#fff', fontWeight: '700', fontSize: 14 },
});
