// app/(more)/leaves.tsx — Leave application list + Apply form
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  View, Text, ScrollView, RefreshControl, TouchableOpacity,
  StyleSheet, ActivityIndicator, TextInput, Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import api from '../../services/api';

const STATUS_COLORS: Record<string, string> = {
  PENDING_TG:  '#f59e0b',
  PENDING_CT:  '#f59e0b',
  APPROVED:    '#10b981',
  REJECTED:    '#ef4444',
  CANCELLED:   '#5a7499',
};

const STATUS_LABELS: Record<string, string> = {
  PENDING_TG: 'Pending (TG)',
  PENDING_CT: 'Pending (CT)',
  APPROVED:   'Approved',
  REJECTED:   'Rejected',
  CANCELLED:  'Cancelled',
};

export default function LeavesScreen() {
  const [showForm, setShowForm] = useState(false);
  const queryClient = useQueryClient();

  const { data, isLoading, refetch, isRefetching } = useQuery({
    queryKey: ['leaves'],
    queryFn:  () => api.get('/leaves/').then(r => r.data),
  });

  const [startDate, setStartDate]   = useState('');
  const [endDate,   setEndDate]     = useState('');
  const [reason,    setReason]      = useState('');
  const [leaveType, setLeaveType]   = useState('multi_day');

  const mutation = useMutation({
    mutationFn: () => api.post('/leaves/apply', {
      start_date: startDate, end_date: endDate,
      reason, leave_type: leaveType,
    }),
    onSuccess: () => {
      Alert.alert('✅ Submitted', 'Your leave application has been submitted.');
      setShowForm(false); setStartDate(''); setEndDate(''); setReason('');
      queryClient.invalidateQueries({ queryKey: ['leaves'] });
    },
    onError: (err: any) => {
      Alert.alert('Error', err?.response?.data?.error ?? 'Failed to submit leave.');
    },
  });

  return (
    <SafeAreaView style={s.safe}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn}>
          <Ionicons name="arrow-back" size={20} color="#3b82f6" />
        </TouchableOpacity>
        <Text style={s.pageTitle}>Leave Applications</Text>
        <TouchableOpacity style={s.applyBtn} onPress={() => setShowForm(!showForm)}>
          <Ionicons name={showForm ? 'close' : 'add'} size={18} color="#fff" />
          <Text style={s.applyBtnText}>{showForm ? 'Cancel' : 'Apply'}</Text>
        </TouchableOpacity>
      </View>

      <ScrollView
        refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} tintColor="#3b82f6" />}
        showsVerticalScrollIndicator={false}
      >
        {/* Apply Form */}
        {showForm && (
          <View style={s.form}>
            <Text style={s.formTitle}>New Leave Application</Text>

            <Text style={s.label}>Leave Type</Text>
            <View style={s.typeRow}>
              {['single_day', 'multi_day', 'medical', 'emergency'].map(t => (
                <TouchableOpacity
                  key={t}
                  style={[s.typeBtn, leaveType === t && s.typeBtnActive]}
                  onPress={() => setLeaveType(t)}
                >
                  <Text style={[s.typeBtnText, leaveType === t && s.typeBtnTextActive]}>
                    {t.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            <Text style={s.label}>Start Date (YYYY-MM-DD)</Text>
            <TextInput style={s.input} placeholder="2024-05-10" placeholderTextColor="#5a7499"
              value={startDate} onChangeText={setStartDate} />

            <Text style={s.label}>End Date (YYYY-MM-DD)</Text>
            <TextInput style={s.input} placeholder="2024-05-12" placeholderTextColor="#5a7499"
              value={endDate} onChangeText={setEndDate} />

            <Text style={s.label}>Reason</Text>
            <TextInput
              style={[s.input, s.textarea]}
              placeholder="Reason for leave..."
              placeholderTextColor="#5a7499"
              value={reason}
              onChangeText={setReason}
              multiline numberOfLines={4}
            />

            <TouchableOpacity
              style={[s.submitBtn, mutation.isPending && s.submitBtnDisabled]}
              onPress={() => mutation.mutate()}
              disabled={mutation.isPending || !startDate || !endDate || !reason}
            >
              {mutation.isPending
                ? <ActivityIndicator color="#fff" />
                : <Text style={s.submitBtnText}>Submit Application</Text>
              }
            </TouchableOpacity>
          </View>
        )}

        {/* Leave List */}
        {isLoading ? (
          <View style={s.loader}><ActivityIndicator size="large" color="#3b82f6" /></View>
        ) : data?.leaves?.length === 0 ? (
          <View style={s.empty}>
            <Ionicons name="walk-outline" size={48} color="#5a7499" />
            <Text style={s.emptyText}>No leave applications yet</Text>
          </View>
        ) : (
          <View style={s.section}>
            {data?.leaves?.map((l: any) => {
              const color = STATUS_COLORS[l.status] ?? '#5a7499';
              return (
                <View key={l.id} style={[s.leaveCard, { borderLeftColor: color }]}>
                  <View style={s.leaveHeader}>
                    <Text style={s.leaveType}>
                      {l.leave_type?.replace('_', ' ').replace(/\b\w/g, (c: string) => c.toUpperCase())}
                    </Text>
                    <View style={[s.statusBadge, { backgroundColor: color + '22' }]}>
                      <Text style={[s.statusText, { color }]}>{STATUS_LABELS[l.status] ?? l.status}</Text>
                    </View>
                  </View>
                  <Text style={s.leaveDates}>{l.start_date} → {l.end_date}</Text>
                  {l.reason && <Text style={s.leaveReason}>{l.reason}</Text>}
                  <Text style={s.leaveDate}>Applied: {new Date(l.created_at).toLocaleDateString('en-IN')}</Text>
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
  safe:           { flex: 1, backgroundColor: '#050d1a' },
  header:         { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingTop: 12, paddingBottom: 8, gap: 10 },
  backBtn:        { padding: 6 },
  pageTitle:      { color: '#f0f4ff', fontSize: 20, fontWeight: '700', flex: 1 },
  applyBtn:       { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#1a56db', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 8 },
  applyBtnText:   { color: '#fff', fontWeight: '700', fontSize: 13 },

  form:           { margin: 16, backgroundColor: '#0d1f3c', borderRadius: 16, padding: 16, borderWidth: 1, borderColor: 'rgba(59,130,246,0.15)' },
  formTitle:      { color: '#f0f4ff', fontSize: 16, fontWeight: '700', marginBottom: 14 },
  label:          { color: '#8ba4c7', fontSize: 11, fontWeight: '600', marginBottom: 6, letterSpacing: 0.5, textTransform: 'uppercase' },
  input:          { backgroundColor: '#0b1830', borderRadius: 10, borderWidth: 1, borderColor: 'rgba(90,116,153,0.3)', paddingHorizontal: 12, paddingVertical: 10, color: '#e2e8f0', fontSize: 14, marginBottom: 12 },
  textarea:       { height: 90, textAlignVertical: 'top' },
  typeRow:        { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 12 },
  typeBtn:        { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8, backgroundColor: '#0b1830', borderWidth: 1, borderColor: 'rgba(90,116,153,0.3)' },
  typeBtnActive:  { backgroundColor: '#1a56db22', borderColor: '#1a56db' },
  typeBtnText:    { color: '#5a7499', fontSize: 12, fontWeight: '600' },
  typeBtnTextActive: { color: '#3b82f6' },
  submitBtn:      { backgroundColor: '#10b981', borderRadius: 12, paddingVertical: 14, alignItems: 'center' },
  submitBtnDisabled: { opacity: 0.5 },
  submitBtnText:  { color: '#fff', fontWeight: '800', fontSize: 15 },

  section:        { paddingHorizontal: 16, paddingTop: 8 },
  loader:         { paddingTop: 80, alignItems: 'center' },
  empty:          { alignItems: 'center', paddingTop: 80, gap: 12 },
  emptyText:      { color: '#5a7499', fontSize: 14 },

  leaveCard:      { backgroundColor: '#0d1f3c', borderRadius: 14, padding: 14, marginBottom: 10, borderLeftWidth: 3 },
  leaveHeader:    { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 },
  leaveType:      { color: '#f0f4ff', fontSize: 14, fontWeight: '700' },
  statusBadge:    { borderRadius: 8, paddingHorizontal: 8, paddingVertical: 3 },
  statusText:     { fontSize: 11, fontWeight: '700' },
  leaveDates:     { color: '#3b82f6', fontSize: 13, fontWeight: '600', marginBottom: 4 },
  leaveReason:    { color: '#8ba4c7', fontSize: 13, marginBottom: 4 },
  leaveDate:      { color: '#5a7499', fontSize: 11 },
});
