// app/(more)/mark-attendance.tsx — Teacher marks attendance screen
import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet,
  ActivityIndicator, Alert, Switch,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { router, useLocalSearchParams } from 'expo-router';
import api from '../../services/api';

export default function MarkAttendanceScreen() {
  const { subject_id, subject_name } = useLocalSearchParams<{ subject_id: string; subject_name: string }>();
  const queryClient = useQueryClient();
  const today = new Date().toISOString().split('T')[0];
  const [attendance, setAttendance] = useState<Record<number, boolean>>({});
  const [allMode, setAllMode] = useState<'none' | 'all-p' | 'all-a'>('none');

  const { data, isLoading } = useQuery({
    queryKey: ['students-for-att', subject_id, today],
    queryFn:  () => api.get(`/attendance/students/${subject_id}?date=${today}`).then(r => r.data),
    enabled:  !!subject_id,
  });

  // Initialize attendance from existing data
  useEffect(() => {
    if (data?.students) {
      const init: Record<number, boolean> = {};
      data.students.forEach((s: any) => {
        init[s.id] = s.present ?? true; // default present
      });
      setAttendance(init);
    }
  }, [data]);

  const setAll = (present: boolean) => {
    const next: Record<number, boolean> = {};
    data?.students.forEach((s: any) => { next[s.id] = present; });
    setAttendance(next);
    setAllMode(present ? 'all-p' : 'all-a');
  };

  const toggle = (id: number) => {
    setAttendance(prev => ({ ...prev, [id]: !prev[id] }));
    setAllMode('none');
  };

  const mutation = useMutation({
    mutationFn: () => api.post('/attendance/mark', {
      subject_id: parseInt(subject_id),
      date: today,
      records: Object.entries(attendance).map(([id, present]) => ({
        student_id: parseInt(id), present
      })),
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['attendance-subjects'] });
      Alert.alert('✅ Saved', 'Attendance saved successfully.', [
        { text: 'OK', onPress: () => router.back() }
      ]);
    },
    onError: (err: any) => {
      Alert.alert('Error', err?.response?.data?.error ?? 'Failed to save attendance.');
    },
  });

  const present = Object.values(attendance).filter(Boolean).length;
  const total   = data?.students?.length ?? 0;
  const absent  = total - present;

  return (
    <SafeAreaView style={s.safe}>
      {/* Header */}
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn}>
          <Ionicons name="arrow-back" size={20} color="#3b82f6" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={s.headerTitle}>{subject_name}</Text>
          <Text style={s.headerDate}>{today} • Mark Attendance</Text>
        </View>
      </View>

      {/* Stats Bar */}
      <View style={s.statsBar}>
        <View style={s.statItem}><Text style={s.statVal}>{total}</Text><Text style={s.statLbl}>Total</Text></View>
        <View style={s.statItem}><Text style={[s.statVal, { color: '#10b981' }]}>{present}</Text><Text style={s.statLbl}>Present</Text></View>
        <View style={s.statItem}><Text style={[s.statVal, { color: '#ef4444' }]}>{absent}</Text><Text style={s.statLbl}>Absent</Text></View>
      </View>

      {/* All P / All A buttons */}
      <View style={s.bulkRow}>
        <TouchableOpacity style={[s.bulkBtn, s.bulkPresent, allMode === 'all-p' && s.bulkActive]} onPress={() => setAll(true)}>
          <Ionicons name="checkmark-circle" size={16} color="#10b981" />
          <Text style={[s.bulkText, { color: '#10b981' }]}>All Present</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[s.bulkBtn, s.bulkAbsent, allMode === 'all-a' && s.bulkActiveRed]} onPress={() => setAll(false)}>
          <Ionicons name="close-circle" size={16} color="#ef4444" />
          <Text style={[s.bulkText, { color: '#ef4444' }]}>All Absent</Text>
        </TouchableOpacity>
      </View>

      {/* Student List */}
      {isLoading ? (
        <View style={s.loader}><ActivityIndicator size="large" color="#3b82f6" /></View>
      ) : (
        <ScrollView style={s.list} showsVerticalScrollIndicator={false}>
          {data?.students?.map((student: any) => {
            const isPresent = attendance[student.id] ?? true;
            return (
              <TouchableOpacity
                key={student.id}
                style={[s.studentRow, { borderLeftColor: isPresent ? '#10b981' : '#ef4444' }]}
                onPress={() => toggle(student.id)}
                activeOpacity={0.8}
              >
                <View style={s.studentInfo}>
                  <Text style={s.studentName}>{student.name}</Text>
                  <Text style={s.studentRoll}>Roll: {student.roll_no} {student.batch ? `• Batch ${student.batch}` : ''}</Text>
                </View>
                <View style={[s.statusBadge, { backgroundColor: isPresent ? '#10b98122' : '#ef444422' }]}>
                  <Ionicons name={isPresent ? 'checkmark-circle' : 'close-circle'} size={20} color={isPresent ? '#10b981' : '#ef4444'} />
                  <Text style={[s.statusText, { color: isPresent ? '#10b981' : '#ef4444' }]}>
                    {isPresent ? 'P' : 'A'}
                  </Text>
                </View>
              </TouchableOpacity>
            );
          })}
          <View style={{ height: 100 }} />
        </ScrollView>
      )}

      {/* Save Button */}
      <View style={s.footer}>
        <TouchableOpacity
          style={[s.saveBtn, mutation.isPending && s.saveBtnDisabled]}
          onPress={() => mutation.mutate()}
          disabled={mutation.isPending || isLoading}
        >
          {mutation.isPending ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <>
              <Ionicons name="save-outline" size={18} color="#fff" />
              <Text style={s.saveBtnText}>Save Attendance</Text>
            </>
          )}
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safe:          { flex: 1, backgroundColor: '#050d1a' },
  header:        { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingTop: 12, paddingBottom: 8, gap: 12 },
  backBtn:       { padding: 6 },
  headerTitle:   { color: '#f0f4ff', fontSize: 16, fontWeight: '700' },
  headerDate:    { color: '#5a7499', fontSize: 12, marginTop: 2 },

  statsBar:      { flexDirection: 'row', justifyContent: 'space-around', backgroundColor: '#0d1f3c', marginHorizontal: 16, borderRadius: 12, paddingVertical: 12, marginBottom: 10 },
  statItem:      { alignItems: 'center' },
  statVal:       { color: '#f0f4ff', fontSize: 20, fontWeight: '800' },
  statLbl:       { color: '#5a7499', fontSize: 11 },

  bulkRow:       { flexDirection: 'row', gap: 10, paddingHorizontal: 16, marginBottom: 10 },
  bulkBtn:       { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, borderRadius: 10, paddingVertical: 10, borderWidth: 1 },
  bulkPresent:   { backgroundColor: '#10b98110', borderColor: '#10b98130' },
  bulkAbsent:    { backgroundColor: '#ef444410', borderColor: '#ef444430' },
  bulkActive:    { backgroundColor: '#10b98130', borderColor: '#10b981' },
  bulkActiveRed: { backgroundColor: '#ef444430', borderColor: '#ef4444' },
  bulkText:      { fontWeight: '700', fontSize: 14 },

  loader:        { flex: 1, alignItems: 'center', justifyContent: 'center' },
  list:          { flex: 1, paddingHorizontal: 16 },
  studentRow:    { flexDirection: 'row', alignItems: 'center', backgroundColor: '#0d1f3c', borderRadius: 12, padding: 14, marginBottom: 8, borderLeftWidth: 3 },
  studentInfo:   { flex: 1 },
  studentName:   { color: '#e2e8f0', fontSize: 15, fontWeight: '600' },
  studentRoll:   { color: '#5a7499', fontSize: 12, marginTop: 2 },
  statusBadge:   { flexDirection: 'row', alignItems: 'center', gap: 4, borderRadius: 8, paddingHorizontal: 10, paddingVertical: 6 },
  statusText:    { fontWeight: '800', fontSize: 14 },

  footer:        { paddingHorizontal: 16, paddingVertical: 12 },
  saveBtn:       { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#10b981', borderRadius: 14, height: 54 },
  saveBtnDisabled: { opacity: 0.6 },
  saveBtnText:   { color: '#fff', fontWeight: '800', fontSize: 16 },
});
