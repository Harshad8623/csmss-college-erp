// app/(tabs)/notices.tsx — Notices + Notifications
import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  View, Text, ScrollView, RefreshControl, TouchableOpacity,
  StyleSheet, ActivityIndicator, TextInput,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';

type Tab = 'notices' | 'notifications';

export default function NoticesTab() {
  const [activeTab, setActiveTab] = useState<Tab>('notices');

  return (
    <SafeAreaView style={s.safe}>
      <View style={s.pageHeader}>
        <Text style={s.pageTitle}>Notices & Alerts</Text>
      </View>
      {/* Segment */}
      <View style={s.segment}>
        <TouchableOpacity
          style={[s.segBtn, activeTab === 'notices' && s.segActive]}
          onPress={() => setActiveTab('notices')}
        >
          <Text style={[s.segText, activeTab === 'notices' && s.segActiveText]}>Notices</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[s.segBtn, activeTab === 'notifications' && s.segActive]}
          onPress={() => setActiveTab('notifications')}
        >
          <Text style={[s.segText, activeTab === 'notifications' && s.segActiveText]}>Notifications</Text>
        </TouchableOpacity>
      </View>

      {activeTab === 'notices' ? <NoticesList /> : <NotificationsList />}
    </SafeAreaView>
  );
}

function NoticesList() {
  const [page, setPage] = useState(1);
  const { data, isLoading, refetch, isRefetching } = useQuery({
    queryKey: ['notices', page],
    queryFn:  () => api.get(`/notices/?page=${page}`).then(r => r.data),
  });

  return (
    <ScrollView
      refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} tintColor="#3b82f6" />}
      showsVerticalScrollIndicator={false}
    >
      {isLoading ? (
        <View style={s.loader}><ActivityIndicator size="large" color="#3b82f6" /></View>
      ) : (
        <View style={s.section}>
          {data?.notices?.length === 0 && (
            <View style={s.empty}>
              <Ionicons name="megaphone-outline" size={48} color="#5a7499" />
              <Text style={s.emptyText}>No notices posted</Text>
            </View>
          )}
          {data?.notices?.map((n: any) => (
            <View key={n.id} style={[s.noticeCard, n.is_urgent && s.urgentCard]}>
              {n.is_urgent && (
                <View style={s.urgentBadge}>
                  <Ionicons name="alert-circle" size={12} color="#ef4444" />
                  <Text style={s.urgentText}>URGENT</Text>
                </View>
              )}
              <Text style={s.noticeTitle}>{n.title}</Text>
              <Text style={s.noticeContent} numberOfLines={3}>{n.content}</Text>
              <View style={s.noticeMeta}>
                {n.posted_by && <Text style={s.noticePoster}>📌 {n.posted_by}</Text>}
                <Text style={s.noticeDate}>{new Date(n.created_at).toLocaleDateString('en-IN')}</Text>
              </View>
            </View>
          ))}
          {/* Pagination */}
          {data && data.pages > 1 && (
            <View style={s.pagination}>
              <TouchableOpacity
                style={[s.pageBtn, page <= 1 && s.pageBtnDisabled]}
                onPress={() => setPage(p => Math.max(1, p - 1))}
                disabled={page <= 1}
              >
                <Ionicons name="chevron-back" size={16} color={page <= 1 ? '#3a4d66' : '#3b82f6'} />
              </TouchableOpacity>
              <Text style={s.pageNum}>{page} / {data.pages}</Text>
              <TouchableOpacity
                style={[s.pageBtn, page >= data.pages && s.pageBtnDisabled]}
                onPress={() => setPage(p => Math.min(data.pages, p + 1))}
                disabled={page >= data.pages}
              >
                <Ionicons name="chevron-forward" size={16} color={page >= data.pages ? '#3a4d66' : '#3b82f6'} />
              </TouchableOpacity>
            </View>
          )}
        </View>
      )}
    </ScrollView>
  );
}

function NotificationsList() {
  const queryClient = useQueryClient();
  const { data, isLoading, refetch, isRefetching } = useQuery({
    queryKey: ['notifications-list'],
    queryFn:  () => api.get('/notifications/?per_page=30').then(r => r.data),
  });

  const markAllRead = async () => {
    await api.post('/notifications/mark-read');
    queryClient.invalidateQueries({ queryKey: ['notifications-list'] });
    queryClient.invalidateQueries({ queryKey: ['dashboard'] });
  };

  return (
    <ScrollView
      refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} tintColor="#3b82f6" />}
      showsVerticalScrollIndicator={false}
    >
      {isLoading ? (
        <View style={s.loader}><ActivityIndicator size="large" color="#3b82f6" /></View>
      ) : (
        <View style={s.section}>
          {data?.unread_count > 0 && (
            <TouchableOpacity style={s.markAllBtn} onPress={markAllRead}>
              <Text style={s.markAllText}>Mark all as read ({data.unread_count})</Text>
            </TouchableOpacity>
          )}
          {data?.notifications?.length === 0 && (
            <View style={s.empty}>
              <Ionicons name="notifications-off-outline" size={48} color="#5a7499" />
              <Text style={s.emptyText}>No notifications</Text>
            </View>
          )}
          {data?.notifications?.map((n: any) => (
            <View key={n.id} style={[s.notifRow, !n.is_read && s.notifUnread]}>
              <View style={[s.notifDot, { backgroundColor: n.is_read ? 'transparent' : '#3b82f6' }]} />
              <View style={{ flex: 1 }}>
                <Text style={s.notifMsg}>{n.message}</Text>
                <Text style={s.notifTime}>{new Date(n.created_at).toLocaleDateString('en-IN')}</Text>
              </View>
            </View>
          ))}
        </View>
      )}
    </ScrollView>
  );
}

const s = StyleSheet.create({
  safe:        { flex: 1, backgroundColor: '#050d1a' },
  pageHeader:  { paddingHorizontal: 20, paddingTop: 16, paddingBottom: 4 },
  pageTitle:   { color: '#f0f4ff', fontSize: 22, fontWeight: '700' },
  segment:     { flexDirection: 'row', marginHorizontal: 16, marginVertical: 12, backgroundColor: '#0d1f3c', borderRadius: 12, padding: 4 },
  segBtn:      { flex: 1, paddingVertical: 8, borderRadius: 8, alignItems: 'center' },
  segActive:   { backgroundColor: '#1a56db' },
  segText:     { color: '#5a7499', fontWeight: '600', fontSize: 14 },
  segActiveText: { color: '#fff' },
  section:     { paddingHorizontal: 16, paddingBottom: 20 },
  loader:      { paddingTop: 80, alignItems: 'center' },
  empty:       { alignItems: 'center', paddingTop: 60, gap: 12 },
  emptyText:   { color: '#5a7499', fontSize: 14 },

  noticeCard:  { backgroundColor: '#0d1f3c', borderRadius: 14, padding: 16, marginBottom: 10, borderWidth: 1, borderColor: 'rgba(59,130,246,0.08)' },
  urgentCard:  { borderColor: 'rgba(239,68,68,0.2)' },
  urgentBadge: { flexDirection: 'row', gap: 4, alignItems: 'center', backgroundColor: '#ef444422', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6, alignSelf: 'flex-start', marginBottom: 8 },
  urgentText:  { color: '#ef4444', fontSize: 10, fontWeight: '800', letterSpacing: 0.5 },
  noticeTitle: { color: '#f0f4ff', fontSize: 15, fontWeight: '700', marginBottom: 6 },
  noticeContent: { color: '#8ba4c7', fontSize: 13, lineHeight: 20 },
  noticeMeta:  { flexDirection: 'row', justifyContent: 'space-between', marginTop: 10 },
  noticePoster: { color: '#5a7499', fontSize: 11 },
  noticeDate:  { color: '#3a4d66', fontSize: 11 },

  notifRow:    { flexDirection: 'row', alignItems: 'flex-start', gap: 10, backgroundColor: '#0d1f3c', borderRadius: 10, padding: 12, marginBottom: 6 },
  notifUnread: { borderLeftWidth: 2, borderLeftColor: '#3b82f6' },
  notifDot:    { width: 8, height: 8, borderRadius: 4, marginTop: 4 },
  notifMsg:    { color: '#e2e8f0', fontSize: 14, lineHeight: 20 },
  notifTime:   { color: '#5a7499', fontSize: 11, marginTop: 4 },

  markAllBtn:  { backgroundColor: '#1a56db22', borderRadius: 10, paddingVertical: 10, alignItems: 'center', marginBottom: 12, borderWidth: 1, borderColor: '#1a56db44' },
  markAllText: { color: '#3b82f6', fontSize: 13, fontWeight: '600' },

  pagination:  { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 16, paddingVertical: 16 },
  pageBtn:     { backgroundColor: '#0d1f3c', borderRadius: 8, padding: 8 },
  pageBtnDisabled: { opacity: 0.4 },
  pageNum:     { color: '#8ba4c7', fontSize: 14, fontWeight: '600' },
});
