// app/(auth)/forgot-password.tsx — OTP-based password reset flow
import { useState } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, ScrollView,
  KeyboardAvoidingView, Platform, ActivityIndicator, Alert, StyleSheet,
} from 'react-native';
import { router } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import api from '../../services/api';

type Step = 'email' | 'otp' | 'reset';

export default function ForgotPasswordScreen() {
  const [step,      setStep]      = useState<Step>('email');
  const [email,     setEmail]     = useState('');
  const [otp,       setOtp]       = useState('');
  const [newPw,     setNewPw]     = useState('');
  const [confirmPw, setConfirmPw] = useState('');
  const [loading,   setLoading]   = useState(false);

  const submitEmail = async () => {
    if (!email.trim()) return;
    setLoading(true);
    try {
      // Uses the web route — same backend handles it
      await api.post('/auth/forgot-password-api', { email: email.trim().toLowerCase() }).catch(() => {});
      Alert.alert('OTP Sent', 'A 6-digit OTP has been sent to your email if it exists.');
      setStep('otp');
    } finally {
      setLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView style={s.flex} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
      <ScrollView contentContainerStyle={s.container} keyboardShouldPersistTaps="handled">
        <TouchableOpacity style={s.back} onPress={() => router.back()}>
          <Ionicons name="arrow-back" size={20} color="#3b82f6" />
          <Text style={s.backText}>Back to Login</Text>
        </TouchableOpacity>

        <View style={s.card}>
          <View style={s.iconCircle}>
            <Ionicons name="mail-outline" size={30} color="#3b82f6" />
          </View>
          <Text style={s.title}>Reset Password</Text>
          <Text style={s.subtitle}>
            Enter your college email. We'll send a 6-digit OTP to reset your password.
          </Text>

          <View style={s.inputGroup}>
            <Text style={s.label}>Email Address</Text>
            <View style={s.inputRow}>
              <Ionicons name="mail-outline" size={18} color="#5a7499" style={s.icon} />
              <TextInput
                style={s.input}
                placeholder="you@csmss.edu"
                placeholderTextColor="#5a7499"
                value={email}
                onChangeText={setEmail}
                keyboardType="email-address"
                autoCapitalize="none"
              />
            </View>
          </View>

          <TouchableOpacity style={[s.btn, loading && s.btnDisabled]} onPress={submitEmail} disabled={loading}>
            {loading ? <ActivityIndicator color="#fff" /> : <Text style={s.btnText}>Send OTP</Text>}
          </TouchableOpacity>

          <Text style={s.hint}>
            💡 If your email is not registered, contact your Class Teacher or HOD to reset your password.
          </Text>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const s = StyleSheet.create({
  flex:       { flex: 1, backgroundColor: '#050d1a' },
  container:  { flexGrow: 1, padding: 20, justifyContent: 'center' },
  back:       { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 20 },
  backText:   { color: '#3b82f6', fontSize: 14 },
  card:       { backgroundColor: '#0d1f3c', borderRadius: 20, padding: 24, borderWidth: 1, borderColor: 'rgba(59,130,246,0.12)', alignItems: 'center' },
  iconCircle: { width: 64, height: 64, borderRadius: 32, backgroundColor: 'rgba(59,130,246,0.1)', alignItems: 'center', justifyContent: 'center', marginBottom: 16 },
  title:      { color: '#f0f4ff', fontSize: 20, fontWeight: '700', marginBottom: 8 },
  subtitle:   { color: '#5a7499', fontSize: 13, textAlign: 'center', lineHeight: 20, marginBottom: 24 },
  inputGroup: { width: '100%', marginBottom: 16 },
  label:      { color: '#8ba4c7', fontSize: 11, fontWeight: '600', marginBottom: 6, letterSpacing: 0.5, textTransform: 'uppercase' },
  inputRow:   { flexDirection: 'row', alignItems: 'center', backgroundColor: '#0b1830', borderRadius: 12, borderWidth: 1, borderColor: 'rgba(90,116,153,0.3)', paddingHorizontal: 12, height: 50 },
  icon:       { marginRight: 8 },
  input:      { flex: 1, color: '#e2e8f0', fontSize: 15 },
  btn:        { backgroundColor: '#1a56db', borderRadius: 12, height: 52, width: '100%', alignItems: 'center', justifyContent: 'center', marginBottom: 16 },
  btnDisabled:{ opacity: 0.7 },
  btnText:    { color: '#fff', fontWeight: '700', fontSize: 16 },
  hint:       { color: '#5a7499', fontSize: 12, textAlign: 'center', lineHeight: 18 },
});
