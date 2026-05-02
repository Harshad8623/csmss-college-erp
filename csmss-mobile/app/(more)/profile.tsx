// app/(more)/profile.tsx — User profile view + edit + change password
import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet,
  ActivityIndicator, TextInput, Alert, Switch,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import api from '../../services/api';
import { useAuthStore } from '../../store/auth.store';

export default function ProfileScreen() {
  const { user, updateUser, logout } = useAuthStore();
  const [editMode,   setEditMode]   = useState(false);
  const [name,       setName]       = useState(user?.name ?? '');
  const [phone,      setPhone]      = useState(user?.phone ?? '');
  const [showPwForm, setShowPwForm] = useState(false);
  const [curPw,      setCurPw]      = useState('');
  const [newPw,      setNewPw]      = useState('');
  const [confPw,     setConfPw]     = useState('');

  const updateMutation = useMutation({
    mutationFn: () => api.patch('/auth/me', { name, phone }),
    onSuccess:  (res) => {
      updateUser(res.data.user);
      setEditMode(false);
      Alert.alert('✅ Saved', 'Profile updated.');
    },
    onError: (err: any) => Alert.alert('Error', err?.response?.data?.error ?? 'Update failed.'),
  });

  const pwMutation = useMutation({
    mutationFn: () => api.post('/auth/change-password', {
      current_password: curPw, new_password: newPw, confirm_password: confPw,
    }),
    onSuccess: () => {
      Alert.alert('✅ Done', 'Password changed successfully.');
      setShowPwForm(false); setCurPw(''); setNewPw(''); setConfPw('');
    },
    onError: (err: any) => Alert.alert('Error', err?.response?.data?.error ?? 'Password change failed.'),
  });

  const ROLE_COLORS: Record<string, string> = {
    STUDENT: '#3b82f6', CR: '#06b6d4', TEACHER: '#10b981',
    CLASS_TEACHER: '#f59e0b', HOD: '#8b5cf6', SUPER_ADMIN: '#ef4444',
  };
  const roleColor = ROLE_COLORS[user?.role ?? ''] ?? '#5a7499';

  return (
    <SafeAreaView style={s.safe}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn}>
          <Ionicons name="arrow-back" size={20} color="#3b82f6" />
        </TouchableOpacity>
        <Text style={s.pageTitle}>My Profile</Text>
        <TouchableOpacity onPress={() => setEditMode(!editMode)} style={s.editBtn}>
          <Ionicons name={editMode ? 'close' : 'pencil-outline'} size={18} color="#3b82f6" />
        </TouchableOpacity>
      </View>

      <ScrollView showsVerticalScrollIndicator={false}>
        {/* Avatar */}
        <View style={s.avatarSection}>
          <View style={[s.avatarCircle, { borderColor: roleColor }]}>
            <Text style={[s.avatarText, { color: roleColor }]}>
              {user?.name?.[0]?.toUpperCase() ?? 'U'}
            </Text>
          </View>
          <Text style={s.userName}>{user?.name}</Text>
          <View style={[s.roleBadge, { backgroundColor: roleColor + '22', borderColor: roleColor + '44' }]}>
            <Text style={[s.roleText, { color: roleColor }]}>
              {user?.role?.replace(/_/g, ' ')}
            </Text>
          </View>
          <Text style={s.userEmail}>{user?.email}</Text>
        </View>

        {/* Info / Edit Section */}
        <View style={s.section}>
          <Text style={s.sectionTitle}>Personal Details</Text>

          <View style={s.infoCard}>
            {editMode ? (
              <>
                <View style={s.field}>
                  <Text style={s.fieldLabel}>Full Name</Text>
                  <TextInput style={s.input} value={name} onChangeText={setName} placeholderTextColor="#5a7499" placeholder="Your name" />
                </View>
                <View style={s.field}>
                  <Text style={s.fieldLabel}>Phone</Text>
                  <TextInput style={s.input} value={phone} onChangeText={setPhone} placeholderTextColor="#5a7499" placeholder="+91 XXXXX XXXXX" keyboardType="phone-pad" />
                </View>
                <TouchableOpacity
                  style={[s.saveBtn, updateMutation.isPending && s.saveBtnDisabled]}
                  onPress={() => updateMutation.mutate()}
                  disabled={updateMutation.isPending}
                >
                  {updateMutation.isPending
                    ? <ActivityIndicator color="#fff" />
                    : <Text style={s.saveBtnText}>Save Changes</Text>
                  }
                </TouchableOpacity>
              </>
            ) : (
              <>
                <InfoRow icon="person-outline"    label="Name"   value={user?.name ?? '—'} />
                <InfoRow icon="mail-outline"       label="Email"  value={user?.email ?? '—'} />
                <InfoRow icon="call-outline"       label="Phone"  value={user?.phone ?? 'Not set'} />
                {user?.student && (
                  <>
                    <InfoRow icon="card-outline"       label="PRN"      value={user.student.prn ?? '—'} />
                    <InfoRow icon="list-outline"       label="Roll No"  value={user.student.roll_no ?? '—'} />
                    <InfoRow icon="school-outline"     label="Class"    value={user.student.class_name ?? '—'} />
                    <InfoRow icon="layers-outline"     label="Batch"    value={user.student.batch ?? '—'} />
                    <InfoRow icon="calendar-outline"   label="Year/Sem" value={`Year ${user.student.year} / Sem ${user.student.semester}`} />
                  </>
                )}
                {user?.teacher && (
                  <>
                    <InfoRow icon="briefcase-outline"  label="Designation"  value={user.teacher.designation ?? '—'} />
                    <InfoRow icon="business-outline"   label="Department"   value={user.teacher.department ?? '—'} />
                  </>
                )}
              </>
            )}
          </View>
        </View>

        {/* Change Password */}
        <View style={s.section}>
          <TouchableOpacity style={s.pwToggle} onPress={() => setShowPwForm(!showPwForm)}>
            <Ionicons name="lock-closed-outline" size={16} color="#f59e0b" />
            <Text style={s.pwToggleText}>Change Password</Text>
            <Ionicons name={showPwForm ? 'chevron-up' : 'chevron-down'} size={16} color="#5a7499" />
          </TouchableOpacity>

          {showPwForm && (
            <View style={s.pwForm}>
              <TextInput style={s.input} placeholder="Current password" placeholderTextColor="#5a7499"
                value={curPw} onChangeText={setCurPw} secureTextEntry />
              <TextInput style={s.input} placeholder="New password (min 8 chars)" placeholderTextColor="#5a7499"
                value={newPw} onChangeText={setNewPw} secureTextEntry />
              <TextInput style={s.input} placeholder="Confirm new password" placeholderTextColor="#5a7499"
                value={confPw} onChangeText={setConfPw} secureTextEntry />
              <TouchableOpacity
                style={[s.saveBtn, { backgroundColor: '#f59e0b' }, pwMutation.isPending && s.saveBtnDisabled]}
                onPress={() => pwMutation.mutate()}
                disabled={pwMutation.isPending || !curPw || !newPw || !confPw}
              >
                {pwMutation.isPending
                  ? <ActivityIndicator color="#fff" />
                  : <Text style={s.saveBtnText}>Change Password</Text>
                }
              </TouchableOpacity>
            </View>
          )}
        </View>

        {/* Logout */}
        <View style={s.section}>
          <TouchableOpacity style={s.logoutBtn} onPress={logout}>
            <Ionicons name="log-out-outline" size={18} color="#ef4444" />
            <Text style={s.logoutText}>Log Out</Text>
          </TouchableOpacity>
        </View>

        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

function InfoRow({ icon, label, value }: { icon: any; label: string; value: string }) {
  return (
    <View style={ir.row}>
      <Ionicons name={icon} size={16} color="#5a7499" />
      <Text style={ir.label}>{label}</Text>
      <Text style={ir.value}>{value}</Text>
    </View>
  );
}

const ir = StyleSheet.create({
  row:   { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: 'rgba(90,116,153,0.1)' },
  label: { color: '#5a7499', fontSize: 13, width: 90 },
  value: { color: '#e2e8f0', fontSize: 14, fontWeight: '500', flex: 1 },
});

const s = StyleSheet.create({
  safe:        { flex: 1, backgroundColor: '#050d1a' },
  header:      { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingTop: 12, paddingBottom: 8, gap: 10 },
  backBtn:     { padding: 6 },
  pageTitle:   { color: '#f0f4ff', fontSize: 20, fontWeight: '700', flex: 1 },
  editBtn:     { padding: 8 },
  avatarSection: { alignItems: 'center', paddingVertical: 24, gap: 6 },
  avatarCircle:{ width: 80, height: 80, borderRadius: 40, backgroundColor: '#0d1f3c', alignItems: 'center', justifyContent: 'center', borderWidth: 3 },
  avatarText:  { fontSize: 32, fontWeight: '800' },
  userName:    { color: '#f0f4ff', fontSize: 20, fontWeight: '700' },
  roleBadge:   { borderRadius: 10, paddingHorizontal: 12, paddingVertical: 4, borderWidth: 1 },
  roleText:    { fontSize: 12, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.5 },
  userEmail:   { color: '#5a7499', fontSize: 13 },
  section:     { paddingHorizontal: 16, marginBottom: 8 },
  sectionTitle:{ color: '#8ba4c7', fontSize: 11, fontWeight: '700', letterSpacing: 0.8, textTransform: 'uppercase', marginBottom: 10 },
  infoCard:    { backgroundColor: '#0d1f3c', borderRadius: 14, padding: 14 },
  field:       { marginBottom: 12 },
  fieldLabel:  { color: '#8ba4c7', fontSize: 11, fontWeight: '600', marginBottom: 6, letterSpacing: 0.5, textTransform: 'uppercase' },
  input:       { backgroundColor: '#0b1830', borderRadius: 10, borderWidth: 1, borderColor: 'rgba(90,116,153,0.3)', paddingHorizontal: 12, paddingVertical: 10, color: '#e2e8f0', fontSize: 14, marginBottom: 8 },
  saveBtn:     { backgroundColor: '#1a56db', borderRadius: 12, paddingVertical: 12, alignItems: 'center', marginTop: 4 },
  saveBtnDisabled: { opacity: 0.5 },
  saveBtnText: { color: '#fff', fontWeight: '800', fontSize: 15 },
  pwToggle:    { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#0d1f3c', borderRadius: 12, padding: 14 },
  pwToggleText:{ color: '#f0f4ff', fontSize: 14, fontWeight: '600', flex: 1 },
  pwForm:      { backgroundColor: '#0d1f3c', borderRadius: 14, padding: 14, marginTop: 8 },
  logoutBtn:   { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#ef444422', borderRadius: 12, paddingVertical: 14, borderWidth: 1, borderColor: 'rgba(239,68,68,0.2)' },
  logoutText:  { color: '#ef4444', fontWeight: '700', fontSize: 15 },
});
