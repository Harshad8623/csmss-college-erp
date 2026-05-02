// app/(auth)/login.tsx — Login Screen
import { useState } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, ScrollView,
  KeyboardAvoidingView, Platform, ActivityIndicator, Alert,
  StyleSheet,
} from 'react-native';
import { router } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useAuthStore } from '../../store/auth.store';
import { API_BASE } from '../../services/api';

export default function LoginScreen() {
  const { login } = useAuthStore();
  const [email,    setEmail]    = useState('');
  const [password, setPassword] = useState('');
  const [showPw,   setShowPw]   = useState(false);
  const [loading,  setLoading]  = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  const handleLogin = async () => {
    if (!email.trim() || !password) {
      setErrorMsg('Please enter email and password');
      return;
    }
    setErrorMsg('');
    setLoading(true);
    try {
      await login(email.trim().toLowerCase(), password);
      // AuthGate in _layout.tsx handles redirect
    } catch (err: any) {
      // Network error — cannot reach the server at all
      if (!err.response) {
        setErrorMsg(
          `❌ Cannot reach server.\n\nServer URL: ${API_BASE}\n\n` +
          `Make sure:\n1. Flask is running (python run.py)\n2. Phone & PC on same WiFi\n3. URL has correct IP`
        );
      } else {
        // Server responded with an error
        const msg = err.response.data?.error ?? `Server error ${err.response.status}`;
        setErrorMsg(`❌ ${msg}`);
      }
    } finally {
      setLoading(false);
    }
  };


  return (
    <KeyboardAvoidingView
      style={s.flex}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <ScrollView
        contentContainerStyle={s.container}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        {/* Background gradient-like overlay */}
        <View style={s.bgBlob1} />
        <View style={s.bgBlob2} />

        {/* Header */}
        <View style={s.header}>
          <View style={s.logoCircle}>
            <Text style={s.logoText}>CSMSS</Text>
          </View>
          <Text style={s.title}>CSMSS College ERP</Text>
          <Text style={s.subtitle}>Chh. Shahu College of Engineering</Text>
          <Text style={s.subtitle2}>Aurangabad, Maharashtra</Text>
        </View>

        {/* Card */}
        <View style={s.card}>
          <Text style={s.cardTitle}>Sign In</Text>
          <Text style={s.cardSubtitle}>Enter your college email and password</Text>

          {/* Email */}
          <View style={s.inputGroup}>
            <Text style={s.label}>Email Address</Text>
            <View style={s.inputRow}>
              <Ionicons name="mail-outline" size={18} color="#5a7499" style={s.inputIcon} />
              <TextInput
                style={s.input}
                placeholder="you@csmss.edu"
                placeholderTextColor="#5a7499"
                value={email}
                onChangeText={setEmail}
                keyboardType="email-address"
                autoCapitalize="none"
                autoCorrect={false}
              />
            </View>
          </View>

          {/* Password */}
          <View style={s.inputGroup}>
            <Text style={s.label}>Password</Text>
            <View style={s.inputRow}>
              <Ionicons name="lock-closed-outline" size={18} color="#5a7499" style={s.inputIcon} />
              <TextInput
                style={[s.input, { flex: 1 }]}
                placeholder="Your password"
                placeholderTextColor="#5a7499"
                value={password}
                onChangeText={setPassword}
                secureTextEntry={!showPw}
                autoCapitalize="none"
              />
              <TouchableOpacity onPress={() => setShowPw(!showPw)} style={s.eyeBtn}>
                <Ionicons name={showPw ? 'eye-off-outline' : 'eye-outline'} size={18} color="#5a7499" />
              </TouchableOpacity>
            </View>
          </View>

          {/* Forgot password */}
          <TouchableOpacity
            style={s.forgotBtn}
            onPress={() => router.push('/(auth)/forgot-password')}
          >
            <Text style={s.forgotText}>Forgot password?</Text>
          </TouchableOpacity>

          {/* Error Message */}
          {errorMsg ? (
            <View style={s.errorBox}>
              <Text style={s.errorText}>{errorMsg}</Text>
            </View>
          ) : null}

          {/* Login Button */}
          <TouchableOpacity
            style={[s.loginBtn, loading && s.loginBtnDisabled]}
            onPress={handleLogin}
            disabled={loading}
            activeOpacity={0.85}
          >
            {loading ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <>
                <Text style={s.loginBtnText}>Sign In</Text>
                <Ionicons name="arrow-forward" size={18} color="#fff" style={{ marginLeft: 8 }} />
              </>
            )}
          </TouchableOpacity>

          {/* Info */}
          <View style={s.infoBox}>
            <Ionicons name="information-circle-outline" size={16} color="#5a7499" />
            <Text style={s.infoText}>
              Contact your HOD or Class Teacher for login credentials.{'\n'}
              Self-registration is disabled.
            </Text>
          </View>
        </View>

        {/* Footer */}
        <View style={s.footer}>
          <Text style={s.footerText}>CSMSS College ERP v1.0</Text>
          <Text style={s.footerSub}>Secure · Role-Based · Real-time</Text>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const s = StyleSheet.create({
  flex:              { flex: 1, backgroundColor: '#050d1a' },
  container:         { flexGrow: 1, padding: 20, justifyContent: 'center', minHeight: '100%' },
  bgBlob1:           { position: 'absolute', width: 300, height: 300, borderRadius: 150, backgroundColor: 'rgba(59,130,246,0.06)', top: -80, right: -80 },
  bgBlob2:           { position: 'absolute', width: 250, height: 250, borderRadius: 125, backgroundColor: 'rgba(139,92,246,0.04)', bottom: 100, left: -100 },

  header:            { alignItems: 'center', marginBottom: 32, marginTop: 60 },
  logoCircle:        { width: 72, height: 72, borderRadius: 36, backgroundColor: 'rgba(59,130,246,0.15)', borderWidth: 2, borderColor: 'rgba(59,130,246,0.4)', alignItems: 'center', justifyContent: 'center', marginBottom: 14 },
  logoText:          { color: '#3b82f6', fontWeight: '800', fontSize: 14, letterSpacing: 1 },
  title:             { color: '#f0f4ff', fontSize: 22, fontWeight: '700', marginBottom: 4 },
  subtitle:          { color: '#8ba4c7', fontSize: 13 },
  subtitle2:         { color: '#5a7499', fontSize: 12, marginTop: 2 },

  card:              { backgroundColor: '#0d1f3c', borderRadius: 20, padding: 24, borderWidth: 1, borderColor: 'rgba(59,130,246,0.12)', marginBottom: 24 },
  cardTitle:         { color: '#f0f4ff', fontSize: 20, fontWeight: '700', marginBottom: 4 },
  cardSubtitle:      { color: '#5a7499', fontSize: 13, marginBottom: 22 },

  inputGroup:        { marginBottom: 16 },
  label:             { color: '#8ba4c7', fontSize: 12, fontWeight: '600', marginBottom: 6, letterSpacing: 0.5, textTransform: 'uppercase' },
  inputRow:          { flexDirection: 'row', alignItems: 'center', backgroundColor: '#0b1830', borderRadius: 12, borderWidth: 1, borderColor: 'rgba(90,116,153,0.3)', paddingHorizontal: 12, height: 50 },
  inputIcon:         { marginRight: 8 },
  input:             { flex: 1, color: '#e2e8f0', fontSize: 15 },
  eyeBtn:            { padding: 4 },

  forgotBtn:         { alignSelf: 'flex-end', marginBottom: 20, marginTop: -8 },
  forgotText:        { color: '#3b82f6', fontSize: 13 },

  loginBtn:          { backgroundColor: '#1a56db', borderRadius: 12, height: 52, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', marginBottom: 20 },
  loginBtnDisabled:  { opacity: 0.7 },
  loginBtnText:      { color: '#fff', fontWeight: '700', fontSize: 16 },

  infoBox:           { flexDirection: 'row', alignItems: 'flex-start', gap: 8, backgroundColor: 'rgba(59,130,246,0.06)', borderRadius: 10, padding: 12, borderWidth: 1, borderColor: 'rgba(59,130,246,0.1)' },
  infoText:          { color: '#5a7499', fontSize: 12, flex: 1, lineHeight: 18 },

  footer:            { alignItems: 'center', paddingBottom: 20 },
  footerText:        { color: '#5a7499', fontSize: 12, fontWeight: '600' },
  footerSub:         { color: '#3a4d66', fontSize: 11, marginTop: 2 },

  errorBox:          { backgroundColor: 'rgba(239,68,68,0.08)', borderRadius: 10, padding: 12, marginBottom: 16, borderWidth: 1, borderColor: 'rgba(239,68,68,0.2)' },
  errorText:         { color: '#ef4444', fontSize: 12, lineHeight: 18 },
});
