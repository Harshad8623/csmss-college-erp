// app/(tabs)/dashboard.tsx — Role-aware Dashboard Screen
import { useQuery } from '@tanstack/react-query';
import {
  View, Text, ScrollView, RefreshControl,
  TouchableOpacity, StyleSheet, ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { useAuthStore } from '../../store/auth.store';

// ── Data fetch ────────────────────────────────────────────────────────────
const fetchDashboard = () => api.get('/dashboard/').then(r => r.data);

// ── Reusable components ───────────────────────────────────────────────────
function StatCard({ icon, label, value, color = '#3b82f6' }: {
  icon: any; label: string; value: string | number; color?: string;
}) {
  return (
    <View style={[s.statCard, { borderLeftColor: color }]}>
      <View style={[s.statIcon, { backgroundColor: color + '22' }]}>
        <Ionicons name={icon} size={20} color={color} />
      </View>
      <Text style={s.statValue}>{value ?? '—'}</Text>
      <Text style={s.statLabel}>{label}</Text>
    </View>
  );
}

function AttBar({ percentage }: { percentage: number }) {
  const pct = Math.min(100, Math.max(0, percentage));
  const color = pct >= 75 ? '#10b981' : pct >= 60 ? '#f59e0b' : '#ef4444';
  return (
    <View>
      <View style={s.barBg}>
        <View style={[s.barFill, { width: `${pct}%`, backgroundColor: color }]} />
      </View>
      <Text style={[s.barLabel, { color }]}>{pct}%</Text>
    </View>
  );
}

function QuickAction({ icon, label, onPress, color = '#3b82f6' }: {
  icon: any; label: string; onPress: () => void; color?: string;
}) {
  return (
    <TouchableOpacity style={s.quickCard} onPress={onPress} activeOpacity={0.8}>
      <View style={[s.quickIcon, { backgroundColor: color + '18' }]}>
        <Ionicons name={icon} size={22} color={color} />
      </View>
      <Text style={s.quickLabel}>{label}</Text>
    </TouchableOpacity>
  );
}

// ── Main Dashboard ─────────────────────────────────────────────────────────
export default function DashboardScreen() {
  const { user, logout } = useAuthStore();
  const { data, isLoading, refetch, isRefetching } = useQuery({
    queryKey: ['dashboard'],
    queryFn:  fetchDashboard,
  });

  const role = user?.role ?? '';

  const greeting = () => {
    const h = new Date().getHours();
    if (h < 12) return 'Good morning';
    if (h < 17) return 'Good afternoon';
    return 'Good evening';
  };

  return (
    <SafeAreaView style={s.safe}>
      <ScrollView
        style={s.scroll}
        refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} tintColor="#3b82f6" />}
        showsVerticalScrollIndicator={false}
      >
        {/* Top Header */}
        <View style={s.header}>
          <View>
            <Text style={s.greeting}>{greeting()},</Text>
            <Text style={s.name}>{user?.name}</Text>
            <Text style={s.roleTag}>{role.replace('_', ' ')}</Text>
          </View>
          <View style={s.headerRight}>
            <TouchableOpacity style={s.notifBtn} onPress={() => router.push('/(tabs)/notices')}>
              <Ionicons name="notifications-outline" size={22} color="#8ba4c7" />
              {(data?.notifications_unread ?? 0) > 0 && (
                <View style={s.badge}>
                  <Text style={s.badgeText}>{data?.notifications_unread}</Text>
                </View>
              )}
            </TouchableOpacity>
            <TouchableOpacity onPress={logout} style={s.logoutBtn}>
              <Ionicons name="log-out-outline" size={22} color="#5a7499" />
            </TouchableOpacity>
          </View>
        </View>

        {isLoading ? (
          <View style={s.loader}>
            <ActivityIndicator size="large" color="#3b82f6" />
            <Text style={s.loaderText}>Loading your dashboard…</Text>
          </View>
        ) : (
          <>
            {/* Student Dashboard */}
            {(role === 'STUDENT' || role === 'CR') && data && (
              <StudentDashboard data={data} />
            )}

            {/* Teacher Dashboard */}
            {role === 'TEACHER' && data && (
              <TeacherDashboard data={data} />
            )}

            {/* Class Teacher Dashboard */}
            {role === 'CLASS_TEACHER' && data && (
              <CTDashboard data={data} />
            )}

            {/* HOD Dashboard */}
            {role === 'HOD' && data && (
              <HODDashboard data={data} />
            )}

            {/* Super Admin Dashboard */}
            {role === 'SUPER_ADMIN' && data && (
              <AdminDashboard data={data} />
            )}
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

// ── Student Dashboard ─────────────────────────────────────────────────────
function StudentDashboard({ data }: { data: any }) {
  return (
    <>
      {/* Attendance Overview */}
      <View style={s.section}>
        <Text style={s.sectionTitle}>My Attendance</Text>
        <View style={[s.attCard, { borderColor: data.attendance.is_defaulter ? '#ef444440' : '#10b98140' }]}>
          {data.attendance.is_defaulter && (
            <View style={s.defaulterBanner}>
              <Ionicons name="warning" size={14} color="#ef4444" />
              <Text style={s.defaulterText}>⚠️ Defaulter — Below 75%</Text>
            </View>
          )}
          <Text style={s.attPct}>{data.attendance.overall_percentage}%</Text>
          <Text style={s.attLabel}>Overall Attendance</Text>
          <AttBar percentage={data.attendance.overall_percentage} />
          <Text style={s.attClass}>{data.class} • Roll No. {data.roll_no}</Text>
        </View>
      </View>

      {/* Subject Attendance */}
      <View style={s.section}>
        <Text style={s.sectionTitle}>Subject-wise</Text>
        {data.attendance.subjects.map((sub: any, i: number) => (
          <View key={i} style={s.subjectRow}>
            <Text style={s.subjectName}>{sub.subject}</Text>
            <View style={s.subjectRight}>
              <AttBar percentage={sub.percentage} />
            </View>
          </View>
        ))}
        <TouchableOpacity style={s.viewAll} onPress={() => router.push('/(tabs)/attendance')}>
          <Text style={s.viewAllText}>View all subjects →</Text>
        </TouchableOpacity>
      </View>

      {/* Today's Timetable */}
      {data.today_timetable?.length > 0 && (
        <View style={s.section}>
          <Text style={s.sectionTitle}>Today's Schedule</Text>
          {data.today_timetable.map((t: any, i: number) => (
            <View key={i} style={s.ttRow}>
              <View style={s.ttPeriod}>
                <Text style={s.ttPeriodText}>P{t.period}</Text>
              </View>
              <View style={s.ttInfo}>
                <Text style={s.ttSubject}>{t.subject}</Text>
                {t.teacher && <Text style={s.ttTeacher}>{t.teacher}</Text>}
              </View>
              {t.batch && <Text style={s.ttBatch}>{t.batch}</Text>}
            </View>
          ))}
        </View>
      )}

      {/* Pending Assignments */}
      {data.pending_assignments?.length > 0 && (
        <View style={s.section}>
          <Text style={s.sectionTitle}>Pending Assignments</Text>
          {data.pending_assignments.map((a: any, i: number) => (
            <TouchableOpacity key={i} style={s.assignCard} onPress={() => router.push('/(more)/assignments')}>
              <Ionicons name="document-text-outline" size={16} color="#f59e0b" />
              <View style={s.assignInfo}>
                <Text style={s.assignTitle}>{a.title}</Text>
                <Text style={s.assignSub}>{a.subject} • Due {a.due_date}</Text>
              </View>
              <Ionicons name="chevron-forward" size={16} color="#5a7499" />
            </TouchableOpacity>
          ))}
        </View>
      )}

      {/* Quick Actions */}
      <View style={s.section}>
        <Text style={s.sectionTitle}>Quick Actions</Text>
        <View style={s.quickGrid}>
          <QuickAction icon="bar-chart-outline" label="My Marks"      onPress={() => router.push('/(tabs)/marks')}             color="#3b82f6" />
          <QuickAction icon="calendar-outline"  label="Timetable"     onPress={() => router.push('/(more)/timetable')}          color="#8b5cf6" />
          <QuickAction icon="document-outline"  label="Apply Leave"   onPress={() => router.push('/(more)/leaves')}             color="#10b981" />
          <QuickAction icon="alert-circle"      label="Grievance"     onPress={() => router.push('/(more)/grievances')}         color="#f59e0b" />
          <QuickAction icon="ribbon-outline"    label="Certificate"   onPress={() => router.push('/(more)/certificates')}       color="#06b6d4" />
          <QuickAction icon="person-outline"    label="My Profile"    onPress={() => router.push('/(more)/profile')}            color="#ec4899" />
        </View>
      </View>
    </>
  );
}

// ── Teacher Dashboard ─────────────────────────────────────────────────────
function TeacherDashboard({ data }: { data: any }) {
  return (
    <>
      <View style={s.statsRow}>
        <StatCard icon="book-outline"        label="Subjects"     value={data.subjects_count}       color="#3b82f6" />
        <StatCard icon="checkmark-outline"   label="Marked Today" value={data.marked_today}         color="#10b981" />
        <StatCard icon="people-outline"      label="TG Students"  value={data.tg_students}          color="#8b5cf6" />
        <StatCard icon="mail-outline"        label="Submissions"  value={data.pending_submissions}  color="#f59e0b" />
      </View>

      <View style={s.section}>
        <Text style={s.sectionTitle}>My Subjects</Text>
        {data.subjects?.map((sub: any, i: number) => (
          <View key={i} style={s.subjectCard}>
            <View style={s.subjectCodeBadge}><Text style={s.subjectCode}>{sub.code}</Text></View>
            <View>
              <Text style={s.subjectNameLarge}>{sub.name}</Text>
              <Text style={s.subjectClass}>{sub.class}</Text>
            </View>
          </View>
        ))}
      </View>

      <View style={s.section}>
        <Text style={s.sectionTitle}>Quick Actions</Text>
        <View style={s.quickGrid}>
          <QuickAction icon="checkmark-circle" label="Mark Attendance" onPress={() => router.push('/(tabs)/attendance')} color="#10b981" />
          <QuickAction icon="bar-chart"         label="Upload Marks"    onPress={() => router.push('/(tabs)/marks')}      color="#3b82f6" />
          <QuickAction icon="megaphone-outline" label="Post Notice"     onPress={() => router.push('/(more)/notices/create')} color="#f59e0b" />
          <QuickAction icon="document-outline"  label="Assignments"     onPress={() => router.push('/(more)/assignments')}color="#8b5cf6" />
        </View>
      </View>
    </>
  );
}

// ── Class Teacher Dashboard ───────────────────────────────────────────────
function CTDashboard({ data }: { data: any }) {
  return (
    <>
      <View style={s.classHeader}>
        <Text style={s.className}>{data.class?.name}</Text>
        <Text style={s.classYear}>Year {data.class?.year}</Text>
      </View>
      <View style={s.statsRow}>
        <StatCard icon="people-outline"   label="Students"    value={data.total_students}       color="#3b82f6" />
        <StatCard icon="time-outline"     label="Pending"     value={data.pending_approvals}    color="#f59e0b" />
        <StatCard icon="book-outline"     label="Subjects"    value={data.subjects_count}       color="#8b5cf6" />
        <StatCard icon="checkmark-outline" label="Today"      value={data.subjects_marked_today} color="#10b981" />
      </View>
      <View style={s.section}>
        <Text style={s.sectionTitle}>Quick Actions</Text>
        <View style={s.quickGrid}>
          <QuickAction icon="people"            label="My Students"    onPress={() => router.push('/(more)/students')}    color="#3b82f6" />
          <QuickAction icon="person-add"        label="Approve Users"  onPress={() => router.push('/(more)/approvals')}   color="#10b981" />
          <QuickAction icon="calendar"          label="Timetable"      onPress={() => router.push('/(more)/timetable')}   color="#8b5cf6" />
          <QuickAction icon="alert-circle"      label="Grievances"     onPress={() => router.push('/(more)/grievances')}  color="#f59e0b" />
        </View>
      </View>
    </>
  );
}

// ── HOD Dashboard ─────────────────────────────────────────────────────────
function HODDashboard({ data }: { data: any }) {
  return (
    <>
      <View style={s.statsRow}>
        <StatCard icon="people-outline"   label="Students"    value={data.dept_students}         color="#3b82f6" />
        <StatCard icon="briefcase-outline" label="Teachers"   value={data.dept_teachers}         color="#8b5cf6" />
        <StatCard icon="school-outline"   label="Classes"     value={data.dept_classes}          color="#10b981" />
        <StatCard icon="alert-circle"     label="Grievances"  value={data.pending_grievances}    color="#ef4444" />
      </View>
    </>
  );
}

// ── Admin Dashboard ───────────────────────────────────────────────────────
function AdminDashboard({ data }: { data: any }) {
  return (
    <>
      <View style={s.statsRow}>
        <StatCard icon="people"           label="Students"    value={data.total_students}        color="#3b82f6" />
        <StatCard icon="briefcase"        label="Teachers"    value={data.total_teachers}        color="#8b5cf6" />
        <StatCard icon="school"           label="Classes"     value={data.total_classes}         color="#10b981" />
        <StatCard icon="alert-circle"     label="Grievances"  value={data.pending_grievances}    color="#ef4444" />
      </View>
      <View style={s.section}>
        <Text style={s.sectionTitle}>Admin Actions</Text>
        <View style={s.quickGrid}>
          <QuickAction icon="people"        label="Users"       onPress={() => router.push('/(more)/admin/users')}    color="#3b82f6" />
          <QuickAction icon="person-add"    label="Pending"     onPress={() => router.push('/(more)/approvals')}      color="#f59e0b" />
          <QuickAction icon="school"        label="Classes"     onPress={() => router.push('/(more)/admin/classes')}  color="#8b5cf6" />
          <QuickAction icon="megaphone"     label="Notices"     onPress={() => router.push('/(more)/notices')}        color="#10b981" />
        </View>
      </View>
    </>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────
const s = StyleSheet.create({
  safe:            { flex: 1, backgroundColor: '#050d1a' },
  scroll:          { flex: 1 },

  header:          { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', paddingHorizontal: 20, paddingTop: 16, paddingBottom: 8 },
  greeting:        { color: '#5a7499', fontSize: 13 },
  name:            { color: '#f0f4ff', fontSize: 20, fontWeight: '700' },
  roleTag:         { color: '#3b82f6', fontSize: 11, fontWeight: '600', marginTop: 2, textTransform: 'uppercase', letterSpacing: 0.5 },
  headerRight:     { flexDirection: 'row', alignItems: 'center', gap: 8 },
  notifBtn:        { position: 'relative', padding: 8 },
  badge:           { position: 'absolute', top: 4, right: 4, width: 16, height: 16, borderRadius: 8, backgroundColor: '#ef4444', alignItems: 'center', justifyContent: 'center' },
  badgeText:       { color: '#fff', fontSize: 9, fontWeight: '800' },
  logoutBtn:       { padding: 8 },

  loader:          { alignItems: 'center', paddingTop: 80, gap: 12 },
  loaderText:      { color: '#5a7499', fontSize: 13 },

  section:         { paddingHorizontal: 20, marginTop: 20 },
  sectionTitle:    { color: '#8ba4c7', fontSize: 12, fontWeight: '700', letterSpacing: 0.8, textTransform: 'uppercase', marginBottom: 12 },

  attCard:         { backgroundColor: '#0d1f3c', borderRadius: 16, padding: 20, borderWidth: 1, alignItems: 'center', gap: 6 },
  defaulterBanner: { flexDirection: 'row', gap: 6, alignItems: 'center', backgroundColor: 'rgba(239,68,68,0.1)', paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8, borderWidth: 1, borderColor: 'rgba(239,68,68,0.2)' },
  defaulterText:   { color: '#ef4444', fontSize: 12, fontWeight: '600' },
  attPct:          { color: '#f0f4ff', fontSize: 40, fontWeight: '800' },
  attLabel:        { color: '#5a7499', fontSize: 13 },
  attClass:        { color: '#5a7499', fontSize: 12, marginTop: 4 },

  barBg:           { height: 6, backgroundColor: '#0b1830', borderRadius: 3, width: '100%', overflow: 'hidden', marginVertical: 4 },
  barFill:         { height: 6, borderRadius: 3 },
  barLabel:        { fontSize: 12, fontWeight: '700', textAlign: 'right' },

  statsRow:        { flexDirection: 'row', flexWrap: 'wrap', paddingHorizontal: 16, gap: 10, marginTop: 16 },
  statCard:        { flex: 1, minWidth: '44%', backgroundColor: '#0d1f3c', borderRadius: 14, padding: 14, borderLeftWidth: 3, gap: 4 },
  statIcon:        { width: 36, height: 36, borderRadius: 8, alignItems: 'center', justifyContent: 'center', marginBottom: 4 },
  statValue:       { color: '#f0f4ff', fontSize: 22, fontWeight: '800' },
  statLabel:       { color: '#5a7499', fontSize: 11 },

  subjectRow:      { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12, backgroundColor: '#0d1f3c', borderRadius: 10, padding: 12 },
  subjectName:     { color: '#8ba4c7', fontSize: 13, flex: 1 },
  subjectRight:    { width: 100 },

  subjectCard:     { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: '#0d1f3c', borderRadius: 12, padding: 14, marginBottom: 8 },
  subjectCodeBadge:{ backgroundColor: '#1a56db22', borderRadius: 6, paddingHorizontal: 8, paddingVertical: 4 },
  subjectCode:     { color: '#3b82f6', fontSize: 12, fontWeight: '700' },
  subjectNameLarge:{ color: '#f0f4ff', fontSize: 14, fontWeight: '600' },
  subjectClass:    { color: '#5a7499', fontSize: 12, marginTop: 2 },

  viewAll:         { alignItems: 'flex-end', marginTop: 4 },
  viewAllText:     { color: '#3b82f6', fontSize: 13 },

  ttRow:           { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: '#0d1f3c', borderRadius: 10, padding: 12, marginBottom: 6 },
  ttPeriod:        { width: 32, height: 32, borderRadius: 8, backgroundColor: '#1a56db22', alignItems: 'center', justifyContent: 'center' },
  ttPeriodText:    { color: '#3b82f6', fontWeight: '700', fontSize: 12 },
  ttInfo:          { flex: 1 },
  ttSubject:       { color: '#e2e8f0', fontSize: 14, fontWeight: '600' },
  ttTeacher:       { color: '#5a7499', fontSize: 12 },
  ttBatch:         { backgroundColor: '#8b5cf622', borderRadius: 6, paddingHorizontal: 6, paddingVertical: 2 },

  assignCard:      { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: '#0d1f3c', borderRadius: 10, padding: 12, marginBottom: 6, borderWidth: 1, borderColor: 'rgba(245,158,11,0.1)' },
  assignInfo:      { flex: 1 },
  assignTitle:     { color: '#e2e8f0', fontSize: 14, fontWeight: '600' },
  assignSub:       { color: '#5a7499', fontSize: 12 },

  quickGrid:       { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  quickCard:       { flex: 1, minWidth: '28%', backgroundColor: '#0d1f3c', borderRadius: 14, padding: 14, alignItems: 'center', gap: 8, borderWidth: 1, borderColor: 'rgba(59,130,246,0.08)' },
  quickIcon:       { width: 44, height: 44, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  quickLabel:      { color: '#8ba4c7', fontSize: 11, textAlign: 'center', fontWeight: '600' },

  classHeader:     { paddingHorizontal: 20, paddingTop: 8 },
  className:       { color: '#f0f4ff', fontSize: 18, fontWeight: '700' },
  classYear:       { color: '#5a7499', fontSize: 13 },
});
