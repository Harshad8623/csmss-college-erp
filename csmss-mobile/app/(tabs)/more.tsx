// app/(tabs)/more.tsx — More tab: links to all remaining modules
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { useAuthStore } from '../../store/auth.store';

interface MenuItem {
  icon: any;
  label: string;
  route: string;
  color: string;
  roles?: string[];
}

const ALL_ITEMS: MenuItem[] = [
  { icon: 'calendar-outline',     label: 'Timetable',         route: '/(more)/timetable',          color: '#8b5cf6' },
  { icon: 'document-text-outline',label: 'Assignments',       route: '/(more)/assignments',         color: '#f59e0b' },
  { icon: 'walk-outline',         label: 'Leave Application', route: '/(more)/leaves',              color: '#10b981' },
  { icon: 'alert-circle-outline', label: 'Grievances',        route: '/(more)/grievances',          color: '#ef4444' },
  { icon: 'ribbon-outline',       label: 'Certificates',      route: '/(more)/certificates',        color: '#06b6d4' },
  { icon: 'flask-outline',        label: 'Practicals',        route: '/(more)/sessions',            color: '#a78bfa' },
  { icon: 'analytics-outline',    label: 'Analytics',         route: '/(more)/analytics',           color: '#3b82f6', roles: ['TEACHER', 'CLASS_TEACHER', 'HOD', 'SUPER_ADMIN'] },
  { icon: 'people-outline',       label: 'My Students',       route: '/(more)/students',            color: '#10b981', roles: ['CLASS_TEACHER', 'TEACHER', 'HOD'] },
  { icon: 'person-add-outline',   label: 'Pending Approvals', route: '/(more)/approvals',           color: '#f59e0b', roles: ['CLASS_TEACHER', 'HOD', 'SUPER_ADMIN'] },
  { icon: 'settings-outline',     label: 'User Management',   route: '/(more)/admin/users',         color: '#6366f1', roles: ['HOD', 'SUPER_ADMIN'] },
  { icon: 'person-outline',       label: 'My Profile',        route: '/(more)/profile',             color: '#ec4899' },
];

export default function MoreTab() {
  const role = useAuthStore(s => s.user?.role ?? '');
  const user = useAuthStore(s => s.user);
  const { logout } = useAuthStore();

  const items = ALL_ITEMS.filter(item =>
    !item.roles || item.roles.includes(role)
  );

  // Group into rows of 3
  const rows: MenuItem[][] = [];
  for (let i = 0; i < items.length; i += 3) {
    rows.push(items.slice(i, i + 3));
  }

  return (
    <SafeAreaView style={s.safe}>
      <ScrollView showsVerticalScrollIndicator={false}>
        <View style={s.pageHeader}>
          <Text style={s.pageTitle}>More</Text>
        </View>

        {/* Profile mini card */}
        <TouchableOpacity style={s.profileCard} onPress={() => router.push('/(more)/profile')} activeOpacity={0.8}>
          <View style={s.avatarCircle}>
            <Text style={s.avatarText}>{user?.name?.[0]?.toUpperCase() ?? 'U'}</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={s.profileName}>{user?.name}</Text>
            <Text style={s.profileRole}>{role.replace(/_/g, ' ')}</Text>
            <Text style={s.profileEmail}>{user?.email}</Text>
          </View>
          <Ionicons name="chevron-forward" size={18} color="#5a7499" />
        </TouchableOpacity>

        {/* Grid */}
        <View style={s.section}>
          <Text style={s.sectionTitle}>All Modules</Text>
          {rows.map((row, ri) => (
            <View key={ri} style={s.row}>
              {row.map((item) => (
                <TouchableOpacity
                  key={item.label}
                  style={s.gridCard}
                  onPress={() => router.push(item.route as any)}
                  activeOpacity={0.8}
                >
                  <View style={[s.gridIcon, { backgroundColor: item.color + '18' }]}>
                    <Ionicons name={item.icon} size={24} color={item.color} />
                  </View>
                  <Text style={s.gridLabel}>{item.label}</Text>
                </TouchableOpacity>
              ))}
              {/* Fill empty slots */}
              {row.length < 3 && Array.from({ length: 3 - row.length }).map((_, i) => (
                <View key={`empty-${i}`} style={[s.gridCard, { backgroundColor: 'transparent', borderColor: 'transparent' }]} />
              ))}
            </View>
          ))}
        </View>

        {/* Logout */}
        <View style={s.logoutSection}>
          <TouchableOpacity style={s.logoutBtn} onPress={logout} activeOpacity={0.8}>
            <Ionicons name="log-out-outline" size={18} color="#ef4444" />
            <Text style={s.logoutText}>Log Out</Text>
          </TouchableOpacity>
        </View>

        {/* Footer */}
        <Text style={s.footer}>CSMSS College ERP v1.0 • All Rights Reserved</Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safe:        { flex: 1, backgroundColor: '#050d1a' },
  pageHeader:  { paddingHorizontal: 20, paddingTop: 16, paddingBottom: 4 },
  pageTitle:   { color: '#f0f4ff', fontSize: 22, fontWeight: '700' },

  profileCard: { flexDirection: 'row', alignItems: 'center', gap: 14, backgroundColor: '#0d1f3c', borderRadius: 16, marginHorizontal: 16, marginTop: 12, marginBottom: 4, padding: 16, borderWidth: 1, borderColor: 'rgba(59,130,246,0.12)' },
  avatarCircle:{ width: 48, height: 48, borderRadius: 24, backgroundColor: '#1a56db33', alignItems: 'center', justifyContent: 'center', borderWidth: 2, borderColor: '#1a56db55' },
  avatarText:  { color: '#3b82f6', fontSize: 20, fontWeight: '800' },
  profileName: { color: '#f0f4ff', fontSize: 15, fontWeight: '700' },
  profileRole: { color: '#3b82f6', fontSize: 11, fontWeight: '600', textTransform: 'uppercase', letterSpacing: 0.5, marginTop: 1 },
  profileEmail:{ color: '#5a7499', fontSize: 12, marginTop: 1 },

  section:     { paddingHorizontal: 16, paddingTop: 16 },
  sectionTitle:{ color: '#8ba4c7', fontSize: 11, fontWeight: '700', letterSpacing: 0.8, textTransform: 'uppercase', marginBottom: 14 },
  row:         { flexDirection: 'row', gap: 10, marginBottom: 10 },
  gridCard:    { flex: 1, backgroundColor: '#0d1f3c', borderRadius: 14, padding: 14, alignItems: 'center', gap: 8, borderWidth: 1, borderColor: 'rgba(59,130,246,0.08)' },
  gridIcon:    { width: 48, height: 48, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  gridLabel:   { color: '#8ba4c7', fontSize: 11, textAlign: 'center', fontWeight: '600' },

  logoutSection: { margin: 16, marginTop: 8 },
  logoutBtn:   { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#ef444422', borderRadius: 12, paddingVertical: 14, borderWidth: 1, borderColor: 'rgba(239,68,68,0.2)' },
  logoutText:  { color: '#ef4444', fontWeight: '700', fontSize: 15 },

  footer:      { textAlign: 'center', color: '#3a4d66', fontSize: 11, paddingBottom: 20 },
});
