// app/(more)/grievances.tsx — Submit and track grievances
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

const TYPES = ['academic', 'infrastructure', 'faculty', 'administration', 'ragging', 'other'];
const PRIORITIES = ['low', 'medium', 'high', 'urgent'];
const STATUS_COLORS: Record<string, string> = {
  PENDING: '#f59e0b', APPROVED: '#10b981', REJECTED: '#ef4444', RESOLVED: '#6366f1',
};

export default function GrievancesScreen() {
  const [showForm, setShowForm] = useState(false);
  const [type,     setType]     = useState('academic');
  const [priority, setPriority] = useState('medium');
  const [desc,     setDesc]     = useState('');
  const queryClient = useQueryClient();

  const { data, isLoading, refetch, isRefetching } = useQuery({
    queryKey: ['grievances'],
    queryFn:  () => api.get('/grievances/').then(r => r.data),
  });

  const mutation = useMutation({
    mutationFn: () => api.post('/grievances/create', { type, priority, description: desc }),
    onSuccess: () => {
      Alert.alert('✅ Submitted', 'Grievance submitted. You can track it here.');
      setShowForm(false); setDesc('');
      queryClient.invalidateQueries({ queryKey: ['grievances'] });
    },
    onError: (err: any) => Alert.alert('Error', err?.response?.data?.error ?? 'Failed to submit.'),
  });

  return (
    <SafeAreaView style={s.safe}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn}>
          <Ionicons name="arrow-back" size={20} color="#3b82f6" />
        </TouchableOpacity>
        <Text style={s.pageTitle}>Grievances</Text>
        <TouchableOpacity style={s.newBtn} onPress={() => setShowForm(!showForm)}>
          <Ionicons name={showForm ? 'close' : 'add'} size={18} color="#fff" />
          <Text style={s.newBtnText}>{showForm ? 'Cancel' : 'New'}</Text>
        </TouchableOpacity>
      </View>

      <ScrollView
        refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} tintColor="#3b82f6" />}
        showsVerticalScrollIndicator={false}
      >
        {showForm && (
          <View style={s.form}>
            <Text style={s.formTitle}>Submit Grievance</Text>

            <Text style={s.label}>Type</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 12 }}>
              <View style={s.optRow}>
                {TYPES.map(t => (
                  <TouchableOpacity key={t} style={[s.optBtn, type === t && s.optBtnActive]} onPress={() => setType(t)}>
                    <Text style={[s.optText, type === t && s.optTextActive]}>
                      {t.charAt(0).toUpperCase() + t.slice(1)}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
            </ScrollView>

            <Text style={s.label}>Priority</Text>
            <View style={s.priorityRow}>
              {PRIORITIES.map(p => {
                const colors: Record<string, string> = { low: '#10b981', medium: '#f59e0b', high: '#ef4444', urgent: '#8b5cf6' };
                const c = colors[p];
                return (
                  <TouchableOpacity
                    key={p}
                    style={[s.priorityBtn, { borderColor: priority === p ? c : 'rgba(90,116,153,0.3)', backgroundColor: priority === p ? c + '22' : '#0b1830' }]}
                    onPress={() => setPriority(p)}
                  >
                    <Text style={[s.priorityText, { color: priority === p ? c : '#5a7499' }]}>
                      {p.charAt(0).toUpperCase() + p.slice(1)}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>

            <Text style={s.label}>Description</Text>
            <TextInput
              style={[s.input, s.textarea]}
              placeholder="Describe your grievance in detail..."
              placeholderTextColor="#5a7499"
              value={desc} onChangeText={setDesc}
              multiline numberOfLines={5}
            />

            <TouchableOpacity
              style={[s.submitBtn, (mutation.isPending || !desc) && s.submitBtnDisabled]}
              onPress={() => mutation.mutate()}
              disabled={mutation.isPending || !desc}
            >
              {mutation.isPending
                ? <ActivityIndicator color="#fff" />
                : <Text style={s.submitBtnText}>Submit Grievance</Text>
              }
            </TouchableOpacity>
          </View>
        )}

        {isLoading ? (
          <View style={s.loader}><ActivityIndicator size="large" color="#3b82f6" /></View>
        ) : data?.grievances?.length === 0 ? (
          <View style={s.empty}>
            <Ionicons name="alert-circle-outline" size={48} color="#5a7499" />
            <Text style={s.emptyText}>No grievances submitted</Text>
          </View>
        ) : (
          <View style={s.section}>
            {data?.grievances?.map((g: any) => {
              const color = STATUS_COLORS[g.status] ?? '#5a7499';
              return (
                <View key={g.id} style={[s.card, { borderLeftColor: color }]}>
                  <View style={s.cardHeader}>
                    <Text style={s.cardType}>{g.type?.charAt(0).toUpperCase() + g.type?.slice(1)}</Text>
                    <View style={[s.statusBadge, { backgroundColor: color + '22' }]}>
                      <Text style={[s.statusText, { color }]}>{g.status}</Text>
                    </View>
                  </View>
                  <Text style={s.cardDesc} numberOfLines={3}>{g.description}</Text>
                  {g.comment && (
                    <View style={s.commentBox}>
                      <Ionicons name="chatbubble-outline" size={12} color="#8b5cf6" />
                      <Text style={s.commentText}>{g.comment}</Text>
                    </View>
                  )}
                  <Text style={s.cardDate}>{new Date(g.created_at).toLocaleDateString('en-IN')}</Text>
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
  safe:         { flex: 1, backgroundColor: '#050d1a' },
  header:       { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingTop: 12, paddingBottom: 8, gap: 10 },
  backBtn:      { padding: 6 },
  pageTitle:    { color: '#f0f4ff', fontSize: 20, fontWeight: '700', flex: 1 },
  newBtn:       { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#ef444499', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 8 },
  newBtnText:   { color: '#fff', fontWeight: '700', fontSize: 13 },
  form:         { margin: 16, backgroundColor: '#0d1f3c', borderRadius: 16, padding: 16, borderWidth: 1, borderColor: 'rgba(239,68,68,0.15)' },
  formTitle:    { color: '#f0f4ff', fontSize: 16, fontWeight: '700', marginBottom: 14 },
  label:        { color: '#8ba4c7', fontSize: 11, fontWeight: '600', marginBottom: 6, letterSpacing: 0.5, textTransform: 'uppercase' },
  optRow:       { flexDirection: 'row', gap: 8 },
  optBtn:       { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8, backgroundColor: '#0b1830', borderWidth: 1, borderColor: 'rgba(90,116,153,0.3)' },
  optBtnActive: { backgroundColor: '#ef444422', borderColor: '#ef4444' },
  optText:      { color: '#5a7499', fontSize: 12, fontWeight: '600' },
  optTextActive:{ color: '#ef4444' },
  priorityRow:  { flexDirection: 'row', gap: 8, marginBottom: 12 },
  priorityBtn:  { flex: 1, paddingVertical: 8, borderRadius: 8, borderWidth: 1, alignItems: 'center' },
  priorityText: { fontSize: 12, fontWeight: '700' },
  input:        { backgroundColor: '#0b1830', borderRadius: 10, borderWidth: 1, borderColor: 'rgba(90,116,153,0.3)', paddingHorizontal: 12, paddingVertical: 10, color: '#e2e8f0', fontSize: 14, marginBottom: 12 },
  textarea:     { height: 110, textAlignVertical: 'top' },
  submitBtn:    { backgroundColor: '#ef4444', borderRadius: 12, paddingVertical: 14, alignItems: 'center' },
  submitBtnDisabled: { opacity: 0.5 },
  submitBtnText:{ color: '#fff', fontWeight: '800', fontSize: 15 },
  section:      { paddingHorizontal: 16, paddingTop: 8 },
  loader:       { paddingTop: 80, alignItems: 'center' },
  empty:        { alignItems: 'center', paddingTop: 80, gap: 12 },
  emptyText:    { color: '#5a7499', fontSize: 14 },
  card:         { backgroundColor: '#0d1f3c', borderRadius: 14, padding: 14, marginBottom: 10, borderLeftWidth: 3 },
  cardHeader:   { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 },
  cardType:     { color: '#f0f4ff', fontSize: 14, fontWeight: '700' },
  statusBadge:  { borderRadius: 8, paddingHorizontal: 8, paddingVertical: 3 },
  statusText:   { fontSize: 11, fontWeight: '700' },
  cardDesc:     { color: '#8ba4c7', fontSize: 13, lineHeight: 18, marginBottom: 4 },
  commentBox:   { flexDirection: 'row', gap: 6, alignItems: 'flex-start', backgroundColor: '#8b5cf610', borderRadius: 8, padding: 8, marginBottom: 4 },
  commentText:  { color: '#8b5cf6', fontSize: 12, flex: 1 },
  cardDate:     { color: '#5a7499', fontSize: 11 },
});
