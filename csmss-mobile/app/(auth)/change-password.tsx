// app/(auth)/change-password.tsx — Forced first-login password change
import { useState } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, ScrollView,
  KeyboardAvoidingView, Platform, ActivityIndicator, Alert, StyleSheet,
} from 'react-native';
import { router } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';
import { useAuthStore } from '../../store/auth.store';

export default function ChangePasswordScreen() {
  const { updateUser, logout } = useAuthStore();
  const [newPw,     setNewPw]     = useState('');
  const [confirmPw, setConfirmPw] = useState('');
  const [loading,   setLoading]   = useState(false);
  const [showNew,   setShowNew]   = useState(false);
  const [showConf,  setShowConf]  = useState(false);

  const handleChange = async () => {
    if (newPw.length < 8) {
      Alert.alert('Too Short', 'Password must be at least 8 characters.');
      return;
    }
    if (newPw !== confirmPw) {
      Alert.alert('Mismatch', 'Passwords do not match.');
      return;
    }
    setLoading(true);
    try {
      await api.post('/auth/change-password', {
        new_password: newPw, confirm_password: confirmPw,
      });
      updateUser({ must_change_password: false });
      Alert.alert('✅ Success', 'Password changed! Welcome to CSMSS ERP.', [
        { text: 'Continue', onPress: () => router.replace('/(tabs)/dashboard') },
      ]);
    } catch (err: any) {
      Alert.alert('Error', err?.response?.data?.error ?? 'Something went wrong.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView style={s.flex} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
      <ScrollView contentContainerStyle={s.container} keyboardShouldPersistTaps="handled">
        <View style={s.card}>
          <View style={s.iconCircle}>
            <Ionicons name="shield-checkmark-outline" size={32} color="#f59e0b" />
          </View>
          <Text style={s.title}>Change Your Password</Text>
          <Text style={s.subtitle}>
            Your account was created with a default password.{'\n'}
            Please set a new secure password to continue.
          </Text>

          <View style={s.inputGroup}>
            <Text style={s.label}>New Password</Text>
            <View style={s.inputRow}>
              <Ionicons name="lock-closed-outline" size={18} color="#5a7499" style={s.icon} />
              <TextInput
                style={[s.input, { flex: 1 }]}
                placeholder="Min. 8 characters"
                placeholderTextColor="#5a7499"
                value={newPw}
                onChangeText={setNewPw}
                secureTextEntry={!showNew}
                autoCapitalize="none"
              />
              <TouchableOpacity onPress={() => setShowNew(!showNew)}>
                <Ionicons name={showNew ? 'eye-off-outline' : 'eye-outline'} size={18} color="#5a7499" />
              </TouchableOpacity>
            </View>
          </View>

          <View style={s.inputGroup}>
            <Text style={s.label}>Confirm Password</Text>
            <View style={s.inputRow}>
              <Ionicons name="lock-closed-outline" size={18} color="#5a7499" style={s.icon} />
              <TextInput
                style={[s.input, { flex: 1 }]}
                placeholder="Repeat new password"
                placeholderTextColor="#5a7499"
                value={confirmPw}
                onChangeText={setConfirmPw}
                secureTextEntry={!showConf}
                autoCapitalize="none"
              />
              <TouchableOpacity onPress={() => setShowConf(!showConf)}>
                <Ionicons name={showConf ? 'eye-off-outline' : 'eye-outline'} size={18} color="#5a7499" />
              </TouchableOpacity>
            </View>
          </View>

          <TouchableOpacity style={[s.btn, loading && s.btnDisabled]} onPress={handleChange} disabled={loading}>
            {loading ? <ActivityIndicator color="#fff" /> : <Text style={s.btnText}>Set New Password</Text>}
          </TouchableOpacity>

          <TouchableOpacity onPress={logout} style={s.logoutBtn}>
            <Text style={s.logoutText}>Log out instead</Text>
          </TouchableOpacity>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const s = StyleSheet.create({
  flex:        { flex: 1, backgroundColor: '#050d1a' },
  container:   { flexGrow: 1, padding: 20, justifyContent: 'center' },
  card:        { backgroundColor: '#0d1f3c', borderRadius: 20, padding: 24, borderWidth: 1, borderColor: 'rgba(245,158,11,0.2)', alignItems: 'center' },
  iconCircle:  { width: 64, height: 64, borderRadius: 32, backgroundColor: 'rgba(245,158,11,0.1)', alignItems: 'center', justifyContent: 'center', marginBottom: 16 },
  title:       { color: '#f0f4ff', fontSize: 20, fontWeight: '700', marginBottom: 8, textAlign: 'center' },
  subtitle:    { color: '#5a7499', fontSize: 13, textAlign: 'center', lineHeight: 20, marginBottom: 24 },
  inputGroup:  { width: '100%', marginBottom: 16 },
  label:       { color: '#8ba4c7', fontSize: 11, fontWeight: '600', marginBottom: 6, letterSpacing: 0.5, textTransform: 'uppercase' },
  inputRow:    { flexDirection: 'row', alignItems: 'center', backgroundColor: '#0b1830', borderRadius: 12, borderWidth: 1, borderColor: 'rgba(90,116,153,0.3)', paddingHorizontal: 12, height: 50 },
  icon:        { marginRight: 8 },
  input:       { color: '#e2e8f0', fontSize: 15 },
  btn:         { backgroundColor: '#f59e0b', borderRadius: 12, height: 52, width: '100%', alignItems: 'center', justifyContent: 'center', marginTop: 8, marginBottom: 12 },
  btnDisabled: { opacity: 0.7 },
  btnText:     { color: '#050d1a', fontWeight: '800', fontSize: 16 },
  logoutBtn:   { paddingVertical: 8 },
  logoutText:  { color: '#5a7499', fontSize: 13 },
});
