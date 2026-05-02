// app/(more)/create-notice.tsx — Teacher/Admin posts a notice
import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet,
  ActivityIndicator, TextInput, Alert, Switch,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import api from '../../services/api';

const AUDIENCE = [
  { key: 'all',      label: 'Everyone',        icon: 'people-outline' },
  { key: 'students', label: 'Students Only',   icon: 'school-outline' },
  { key: 'teachers', label: 'Teachers Only',   icon: 'briefcase-outline' },
  { key: 'class',    label: 'My Class',        icon: 'people-circle-outline' },
];

export default function CreateNoticeScreen() {
  const [title,     setTitle]    = useState('');
  const [content,   setContent]  = useState('');
  const [isUrgent,  setIsUrgent] = useState(false);
  const [audience,  setAudience] = useState('all');
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () => api.post('/notices/', {
      title: title.trim(),
      content: content.trim(),
      is_urgent: isUrgent,
      audience,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notices'] });
      Alert.alert('✅ Posted', 'Notice has been posted successfully.', [
        { text: 'OK', onPress: () => router.back() }
      ]);
    },
    onError: (err: any) => Alert.alert('Error', err?.response?.data?.error ?? 'Failed to post notice.'),
  });

  return (
    <SafeAreaView style={s.safe}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn}>
          <Ionicons name="arrow-back" size={20} color="#3b82f6" />
        </TouchableOpacity>
        <Text style={s.pageTitle}>Post Notice</Text>
      </View>

      <ScrollView showsVerticalScrollIndicator={false}>
        <View style={s.form}>
          {/* Urgent Toggle */}
          <View style={s.urgentRow}>
            <View>
              <Text style={s.urgentLabel}>Urgent Notice</Text>
              <Text style={s.urgentSub}>Shows red banner — use for critical announcements</Text>
            </View>
            <Switch
              value={isUrgent}
              onValueChange={setIsUrgent}
              trackColor={{ false: '#0b1830', true: '#ef444460' }}
              thumbColor={isUrgent ? '#ef4444' : '#5a7499'}
            />
          </View>

          {/* Title */}
          <Text style={s.label}>Notice Title *</Text>
          <TextInput
            style={s.input}
            placeholder="e.g. Exam Schedule Change"
            placeholderTextColor="#5a7499"
            value={title}
            onChangeText={setTitle}
            maxLength={200}
          />

          {/* Content */}
          <Text style={s.label}>Notice Content *</Text>
          <TextInput
            style={[s.input, s.textarea]}
            placeholder="Type the full notice content here..."
            placeholderTextColor="#5a7499"
            value={content}
            onChangeText={setContent}
            multiline
            numberOfLines={8}
          />

          {/* Audience */}
          <Text style={s.label}>Target Audience</Text>
          <View style={s.audienceGrid}>
            {AUDIENCE.map(a => (
              <TouchableOpacity
                key={a.key}
                style={[s.audienceCard, audience === a.key && s.audienceCardActive]}
                onPress={() => setAudience(a.key)}
                activeOpacity={0.8}
              >
                <Ionicons
                  name={a.icon}
                  size={20}
                  color={audience === a.key ? '#3b82f6' : '#5a7499'}
                />
                <Text style={[s.audienceText, audience === a.key && s.audienceTextActive]}>
                  {a.label}
                </Text>
              </TouchableOpacity>
            ))}
          </View>

          {/* Preview */}
          {(title || content) && (
            <View style={s.preview}>
              <Text style={s.previewLabel}>Preview</Text>
              <View style={[s.previewCard, isUrgent && s.previewUrgent]}>
                {isUrgent && (
                  <View style={s.urgentBadge}>
                    <Ionicons name="alert-circle" size={12} color="#ef4444" />
                    <Text style={s.urgentBadgeText}>URGENT</Text>
                  </View>
                )}
                <Text style={s.previewTitle}>{title || 'Notice Title'}</Text>
                <Text style={s.previewContent} numberOfLines={3}>
                  {content || 'Notice content will appear here...'}
                </Text>
              </View>
            </View>
          )}

          {/* Post Button */}
          <TouchableOpacity
            style={[
              s.postBtn,
              isUrgent && s.postBtnUrgent,
              (mutation.isPending || !title.trim() || !content.trim()) && s.postBtnDisabled
            ]}
            onPress={() => mutation.mutate()}
            disabled={mutation.isPending || !title.trim() || !content.trim()}
            activeOpacity={0.8}
          >
            {mutation.isPending ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <>
                <Ionicons name="megaphone-outline" size={18} color="#fff" />
                <Text style={s.postBtnText}>
                  {isUrgent ? '⚠️ Post Urgent Notice' : 'Post Notice'}
                </Text>
              </>
            )}
          </TouchableOpacity>
        </View>
        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safe:             { flex: 1, backgroundColor: '#050d1a' },
  header:           { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingTop: 12, paddingBottom: 8, gap: 10 },
  backBtn:          { padding: 6 },
  pageTitle:        { color: '#f0f4ff', fontSize: 20, fontWeight: '700' },
  form:             { padding: 16, gap: 4 },
  urgentRow:        { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', backgroundColor: '#0d1f3c', borderRadius: 14, padding: 14, marginBottom: 16, borderWidth: 1, borderColor: 'rgba(239,68,68,0.1)' },
  urgentLabel:      { color: '#f0f4ff', fontSize: 14, fontWeight: '600' },
  urgentSub:        { color: '#5a7499', fontSize: 11, marginTop: 2, maxWidth: 220 },
  label:            { color: '#8ba4c7', fontSize: 11, fontWeight: '700', letterSpacing: 0.8, textTransform: 'uppercase', marginBottom: 8, marginTop: 8 },
  input:            { backgroundColor: '#0d1f3c', borderRadius: 12, borderWidth: 1, borderColor: 'rgba(59,130,246,0.15)', paddingHorizontal: 14, paddingVertical: 12, color: '#e2e8f0', fontSize: 15, marginBottom: 4 },
  textarea:         { height: 160, textAlignVertical: 'top' },
  audienceGrid:     { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginBottom: 8 },
  audienceCard:     { flex: 1, minWidth: '44%', flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#0d1f3c', borderRadius: 12, padding: 12, borderWidth: 1, borderColor: 'rgba(59,130,246,0.1)' },
  audienceCardActive: { borderColor: '#3b82f6', backgroundColor: '#1a56db18' },
  audienceText:     { color: '#5a7499', fontSize: 12, fontWeight: '600', flex: 1 },
  audienceTextActive: { color: '#3b82f6' },
  preview:          { marginTop: 8, marginBottom: 4 },
  previewLabel:     { color: '#8ba4c7', fontSize: 11, fontWeight: '700', letterSpacing: 0.8, textTransform: 'uppercase', marginBottom: 8 },
  previewCard:      { backgroundColor: '#0d1f3c', borderRadius: 14, padding: 14, borderWidth: 1, borderColor: 'rgba(59,130,246,0.1)' },
  previewUrgent:    { borderColor: 'rgba(239,68,68,0.2)' },
  urgentBadge:      { flexDirection: 'row', gap: 4, alignItems: 'center', backgroundColor: '#ef444422', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6, alignSelf: 'flex-start', marginBottom: 8 },
  urgentBadgeText:  { color: '#ef4444', fontSize: 10, fontWeight: '800', letterSpacing: 0.5 },
  previewTitle:     { color: '#f0f4ff', fontSize: 15, fontWeight: '700', marginBottom: 6 },
  previewContent:   { color: '#8ba4c7', fontSize: 13, lineHeight: 20 },
  postBtn:          { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#1a56db', borderRadius: 14, height: 56, marginTop: 16 },
  postBtnUrgent:    { backgroundColor: '#dc2626' },
  postBtnDisabled:  { opacity: 0.5 },
  postBtnText:      { color: '#fff', fontWeight: '800', fontSize: 16 },
});
