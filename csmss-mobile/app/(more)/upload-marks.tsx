// app/(more)/upload-marks.tsx — Teacher uploads marks for a subject
import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet,
  ActivityIndicator, Alert, TextInput,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { router, useLocalSearchParams } from 'expo-router';
import api from '../../services/api';

const EXAM_TYPES = [
  { key: 'CT1', label: 'CT 1' }, { key: 'CT2', label: 'CT 2' },
  { key: 'CT3', label: 'CT 3' }, { key: 'MID', label: 'Mid Sem' },
  { key: 'END', label: 'End Sem' }, { key: 'PRAC', label: 'Practical' },
  { key: 'IA', label: 'IA' }, { key: 'ORAL', label: 'Oral' },
];

export default function UploadMarksScreen() {
  const { subject_id, subject_name } = useLocalSearchParams<{ subject_id: string; subject_name: string }>();
  const [examType,  setExamType]  = useState('CT1');
  const [maxMarks,  setMaxMarks]  = useState('25');
  const [markMap,   setMarkMap]   = useState<Record<number, string>>({});
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ['marks-students', subject_id, examType],
    queryFn:  () => api.get(`/marks/subject/${subject_id}/students?exam_type=${examType}`).then(r => r.data),
    enabled:  !!subject_id,
  });

  // Pre-fill from existing marks
  useEffect(() => {
    if (data?.students) {
      const init: Record<number, string> = {};
      data.students.forEach((s: any) => {
        if (s.marks !== null) init[s.student_id] = String(s.marks);
      });
      setMarkMap(init);
      if (data.students[0]?.max_marks) setMaxMarks(String(data.students[0].max_marks));
    }
  }, [data]);

  const mutation = useMutation({
    mutationFn: () => api.post('/marks/upload', {
      subject_id: parseInt(subject_id),
      exam_type: examType,
      max_marks: parseFloat(maxMarks),
      records: Object.entries(markMap)
        .filter(([, v]) => v !== '')
        .map(([id, marks]) => ({ student_id: parseInt(id), marks: parseFloat(marks) })),
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['marks-students'] });
      Alert.alert('✅ Saved', 'Marks uploaded successfully.', [
        { text: 'OK', onPress: () => router.back() }
      ]);
    },
    onError: (err: any) => Alert.alert('Error', err?.response?.data?.error ?? 'Failed to save marks.'),
  });

  const filled  = Object.values(markMap).filter(v => v !== '').length;
  const total   = data?.students?.length ?? 0;
  const avg     = filled > 0
    ? (Object.values(markMap).filter(v => v !== '').reduce((a, b) => a + parseFloat(b), 0) / filled).toFixed(1)
    : '—';

  return (
    <SafeAreaView style={s.safe}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn}>
          <Ionicons name="arrow-back" size={20} color="#3b82f6" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={s.headerTitle}>{subject_name}</Text>
          <Text style={s.headerSub}>Upload Marks</Text>
        </View>
      </View>

      {/* Exam Type Selector */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.examScroll} contentContainerStyle={s.examRow}>
        {EXAM_TYPES.map(e => (
          <TouchableOpacity
            key={e.key}
            style={[s.examBtn, examType === e.key && s.examBtnActive]}
            onPress={() => setExamType(e.key)}
          >
            <Text style={[s.examBtnText, examType === e.key && s.examBtnTextActive]}>{e.label}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {/* Max Marks + Stats */}
      <View style={s.statsBar}>
        <View style={s.maxMarksBox}>
          <Text style={s.maxMarksLabel}>Max Marks</Text>
          <TextInput
            style={s.maxMarksInput}
            value={maxMarks}
            onChangeText={setMaxMarks}
            keyboardType="decimal-pad"
          />
        </View>
        <View style={s.statItem}><Text style={[s.statVal, { color: '#3b82f6' }]}>{filled}/{total}</Text><Text style={s.statLbl}>Filled</Text></View>
        <View style={s.statItem}><Text style={[s.statVal, { color: '#10b981' }]}>{avg}</Text><Text style={s.statLbl}>Avg</Text></View>
      </View>

      {isLoading ? (
        <View style={s.loader}><ActivityIndicator size="large" color="#3b82f6" /></View>
      ) : (
        <ScrollView style={s.list} showsVerticalScrollIndicator={false}>
          {data?.students?.map((student: any) => (
            <View key={student.student_id} style={s.studentRow}>
              <View style={s.studentInfo}>
                <Text style={s.studentName}>{student.name}</Text>
                <Text style={s.studentRoll}>Roll: {student.roll_no}</Text>
              </View>
              <View style={s.marksInputBox}>
                <TextInput
                  style={[
                    s.marksInput,
                    markMap[student.student_id] !== undefined && parseFloat(markMap[student.student_id]) > parseFloat(maxMarks)
                      ? s.marksInputError : {}
                  ]}
                  placeholder="—"
                  placeholderTextColor="#5a7499"
                  value={markMap[student.student_id] ?? ''}
                  onChangeText={v => setMarkMap(prev => ({ ...prev, [student.student_id]: v }))}
                  keyboardType="decimal-pad"
                  maxLength={5}
                />
                <Text style={s.maxMarksSlash}>/{maxMarks}</Text>
              </View>
            </View>
          ))}
          <View style={{ height: 100 }} />
        </ScrollView>
      )}

      {/* Save */}
      <View style={s.footer}>
        <TouchableOpacity
          style={[s.saveBtn, (mutation.isPending || filled === 0) && s.saveBtnDisabled]}
          onPress={() => mutation.mutate()}
          disabled={mutation.isPending || filled === 0}
        >
          {mutation.isPending
            ? <ActivityIndicator color="#fff" />
            : <>
                <Ionicons name="cloud-upload-outline" size={18} color="#fff" />
                <Text style={s.saveBtnText}>Upload {filled} Marks</Text>
              </>
          }
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safe:          { flex: 1, backgroundColor: '#050d1a' },
  header:        { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingTop: 12, paddingBottom: 4, gap: 12 },
  backBtn:       { padding: 6 },
  headerTitle:   { color: '#f0f4ff', fontSize: 16, fontWeight: '700' },
  headerSub:     { color: '#5a7499', fontSize: 12 },
  examScroll:    { maxHeight: 52 },
  examRow:       { paddingHorizontal: 16, gap: 8, alignItems: 'center', paddingVertical: 8 },
  examBtn:       { paddingHorizontal: 14, paddingVertical: 7, borderRadius: 20, backgroundColor: '#0d1f3c', borderWidth: 1, borderColor: 'rgba(59,130,246,0.15)' },
  examBtnActive: { backgroundColor: '#1a56db', borderColor: '#1a56db' },
  examBtnText:   { color: '#5a7499', fontWeight: '600', fontSize: 13 },
  examBtnTextActive: { color: '#fff' },
  statsBar:      { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 10, gap: 16, backgroundColor: '#0d1f3c', marginHorizontal: 16, borderRadius: 12, marginBottom: 8 },
  maxMarksBox:   { flex: 1 },
  maxMarksLabel: { color: '#5a7499', fontSize: 10, marginBottom: 2, textTransform: 'uppercase', letterSpacing: 0.5 },
  maxMarksInput: { backgroundColor: '#0b1830', borderRadius: 8, borderWidth: 1, borderColor: 'rgba(90,116,153,0.3)', paddingHorizontal: 10, paddingVertical: 6, color: '#e2e8f0', fontSize: 14, fontWeight: '700', width: 60 },
  statItem:      { alignItems: 'center' },
  statVal:       { fontSize: 18, fontWeight: '800' },
  statLbl:       { color: '#5a7499', fontSize: 10 },
  loader:        { flex: 1, alignItems: 'center', justifyContent: 'center' },
  list:          { flex: 1, paddingHorizontal: 16 },
  studentRow:    { flexDirection: 'row', alignItems: 'center', backgroundColor: '#0d1f3c', borderRadius: 12, padding: 12, marginBottom: 6, gap: 12 },
  studentInfo:   { flex: 1 },
  studentName:   { color: '#e2e8f0', fontSize: 14, fontWeight: '600' },
  studentRoll:   { color: '#5a7499', fontSize: 12, marginTop: 2 },
  marksInputBox: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  marksInput:    { backgroundColor: '#0b1830', borderRadius: 8, borderWidth: 1, borderColor: 'rgba(90,116,153,0.3)', width: 58, paddingHorizontal: 8, paddingVertical: 6, color: '#e2e8f0', fontSize: 15, fontWeight: '700', textAlign: 'center' },
  marksInputError: { borderColor: '#ef4444' },
  maxMarksSlash: { color: '#5a7499', fontSize: 12 },
  footer:        { paddingHorizontal: 16, paddingVertical: 12 },
  saveBtn:       { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#1a56db', borderRadius: 14, height: 54 },
  saveBtnDisabled: { opacity: 0.5 },
  saveBtnText:   { color: '#fff', fontWeight: '800', fontSize: 16 },
});
