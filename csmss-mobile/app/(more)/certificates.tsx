// app/(more)/certificates.tsx — Apply and track bonafide/other certificates
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

const CERT_TYPES = ['bonafide', 'character', 'conduct', 'no_dues', 'migration', 'other'];
const STATUS_COLORS: Record<string, string> = {
  PENDING: '#f59e0b', APPROVED: '#10b981', REJECTED: '#ef4444',
};
const CERT_ICONS: Record<string, any> = {
  bonafide: 'ribbon-outline', character: 'person-outline',
  conduct: 'shield-outline', no_dues: 'checkmark-circle-outline',
  migration: 'airplane-outline', other: 'document-outline',
};

export default function CertificatesScreen() {
  const [showForm, setShowForm] = useState(false);
  const [certType, setCertType] = useState('bonafide');
  const [purpose,  setPurpose]  = useState('');
  const queryClient = useQueryClient();

  const { data, isLoading, refetch, isRefetching } = useQuery({
    queryKey: ['certificates'],
    queryFn:  () => api.get('/certificates/').then(r => r.data),
  });

  const mutation = useMutation({
    mutationFn: () => api.post('/certificates/apply', { type: certType, purpose }),
    onSuccess: () => {
      Alert.alert('✅ Applied', 'Certificate application submitted. You will be notified when it is ready.');
      setShowForm(false); setPurpose('');
      queryClient.invalidateQueries({ queryKey: ['certificates'] });
    },
    onError: (err: any) => Alert.alert('Error', err?.response?.data?.error ?? 'Failed to apply.'),
  });

  return (
    <SafeAreaView style={s.safe}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn}>
          <Ionicons name="arrow-back" size={20} color="#3b82f6" />
        </TouchableOpacity>
        <Text style={s.pageTitle}>Certificates</Text>
        <TouchableOpacity style={s.applyBtn} onPress={() => setShowForm(!showForm)}>
          <Ionicons name={showForm ? 'close' : 'add'} size={18} color="#fff" />
          <Text style={s.applyBtnText}>{showForm ? 'Cancel' : 'Apply'}</Text>
        </TouchableOpacity>
      </View>

      <ScrollView
        refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} tintColor="#3b82f6" />}
        showsVerticalScrollIndicator={false}
      >
        {showForm && (
          <View style={s.form}>
            <Text style={s.formTitle}>Apply for Certificate</Text>

            <Text style={s.label}>Certificate Type</Text>
            <View style={s.typeGrid}>
              {CERT_TYPES.map(t => (
                <TouchableOpacity
                  key={t}
                  style={[s.typeCard, certType === t && s.typeCardActive]}
                  onPress={() => setCertType(t)}
                >
                  <Ionicons name={CERT_ICONS[t]} size={20} color={certType === t ? '#06b6d4' : '#5a7499'} />
                  <Text style={[s.typeCardText, certType === t && s.typeCardTextActive]}>
                    {t.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            <Text style={s.label}>Purpose</Text>
            <TextInput
              style={[s.input, s.textarea]}
              placeholder="e.g. For Bank Account, Passport, Scholarship..."
              placeholderTextColor="#5a7499"
              value={purpose} onChangeText={setPurpose}
              multiline numberOfLines={3}
            />

            <TouchableOpacity
              style={[s.submitBtn, (mutation.isPending || !purpose) && s.submitBtnDisabled]}
              onPress={() => mutation.mutate()}
              disabled={mutation.isPending || !purpose}
            >
              {mutation.isPending
                ? <ActivityIndicator color="#fff" />
                : <Text style={s.submitBtnText}>Submit Application</Text>
              }
            </TouchableOpacity>
          </View>
        )}

        {/* Info Banner */}
        <View style={s.infoBanner}>
          <Ionicons name="information-circle-outline" size={16} color="#06b6d4" />
          <Text style={s.infoText}>
            Approved certificates can be collected from the college office. Allow 2–3 working days.
          </Text>
        </View>

        {isLoading ? (
          <View style={s.loader}><ActivityIndicator size="large" color="#3b82f6" /></View>
        ) : data?.certificates?.length === 0 ? (
          <View style={s.empty}>
            <Ionicons name="ribbon-outline" size={48} color="#5a7499" />
            <Text style={s.emptyText}>No certificate applications yet</Text>
          </View>
        ) : (
          <View style={s.section}>
            {data?.certificates?.map((c: any) => {
              const color = STATUS_COLORS[c.status] ?? '#5a7499';
              return (
                <View key={c.id} style={[s.card, { borderLeftColor: color }]}>
                  <View style={s.cardHeader}>
                    <View style={s.cardLeft}>
                      <Ionicons name={CERT_ICONS[c.type] ?? 'document-outline'} size={18} color="#06b6d4" />
                      <Text style={s.cardType}>
                        {c.type?.replace('_', ' ').replace(/\b\w/g, (l: string) => l.toUpperCase())}
                      </Text>
                    </View>
                    <View style={[s.statusBadge, { backgroundColor: color + '22' }]}>
                      <Text style={[s.statusText, { color }]}>{c.status}</Text>
                    </View>
                  </View>
                  {c.purpose && <Text style={s.cardPurpose}>{c.purpose}</Text>}
                  <Text style={s.cardDate}>Applied: {new Date(c.created_at).toLocaleDateString('en-IN')}</Text>
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
  applyBtn:       { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#0891b2', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 8 },
  applyBtnText:   { color: '#fff', fontWeight: '700', fontSize: 13 },
  form:           { margin: 16, backgroundColor: '#0d1f3c', borderRadius: 16, padding: 16, borderWidth: 1, borderColor: 'rgba(6,182,212,0.15)' },
  formTitle:      { color: '#f0f4ff', fontSize: 16, fontWeight: '700', marginBottom: 14 },
  label:          { color: '#8ba4c7', fontSize: 11, fontWeight: '600', marginBottom: 8, letterSpacing: 0.5, textTransform: 'uppercase' },
  typeGrid:       { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 14 },
  typeCard:       { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#0b1830', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 8, borderWidth: 1, borderColor: 'rgba(90,116,153,0.3)' },
  typeCardActive: { backgroundColor: '#06b6d422', borderColor: '#06b6d4' },
  typeCardText:   { color: '#5a7499', fontSize: 12, fontWeight: '600' },
  typeCardTextActive: { color: '#06b6d4' },
  input:          { backgroundColor: '#0b1830', borderRadius: 10, borderWidth: 1, borderColor: 'rgba(90,116,153,0.3)', paddingHorizontal: 12, paddingVertical: 10, color: '#e2e8f0', fontSize: 14, marginBottom: 12 },
  textarea:       { height: 80, textAlignVertical: 'top' },
  submitBtn:      { backgroundColor: '#0891b2', borderRadius: 12, paddingVertical: 14, alignItems: 'center' },
  submitBtnDisabled: { opacity: 0.5 },
  submitBtnText:  { color: '#fff', fontWeight: '800', fontSize: 15 },
  infoBanner:     { flexDirection: 'row', alignItems: 'flex-start', gap: 8, marginHorizontal: 16, marginVertical: 8, backgroundColor: '#06b6d410', borderRadius: 10, padding: 12, borderWidth: 1, borderColor: '#06b6d420' },
  infoText:       { color: '#8ba4c7', fontSize: 12, flex: 1, lineHeight: 18 },
  section:        { paddingHorizontal: 16, paddingTop: 4 },
  loader:         { paddingTop: 80, alignItems: 'center' },
  empty:          { alignItems: 'center', paddingTop: 60, gap: 12 },
  emptyText:      { color: '#5a7499', fontSize: 14 },
  card:           { backgroundColor: '#0d1f3c', borderRadius: 14, padding: 14, marginBottom: 10, borderLeftWidth: 3 },
  cardHeader:     { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 },
  cardLeft:       { flexDirection: 'row', alignItems: 'center', gap: 8 },
  cardType:       { color: '#f0f4ff', fontSize: 14, fontWeight: '700' },
  statusBadge:    { borderRadius: 8, paddingHorizontal: 8, paddingVertical: 3 },
  statusText:     { fontSize: 11, fontWeight: '700' },
  cardPurpose:    { color: '#8ba4c7', fontSize: 13, marginBottom: 4 },
  cardDate:       { color: '#5a7499', fontSize: 11 },
});
